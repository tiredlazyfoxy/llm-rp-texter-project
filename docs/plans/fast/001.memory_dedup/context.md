# Fast feature 001 — memory_dedup — context

## Problem

The summarization flow's Phase 1 calls `add_memory` repeatedly across compactions to record user-preference facts. Despite current memories being supplied to the LLM in-prompt, it keeps emitting near-duplicates of facts that already exist (and sometimes the same fact twice within one extraction pass). Result: `chat_memories` accumulates redundant rows and the memory store loses signal over time.

## Approach

Insert a compaction step between Phase 1 (memory extraction) and Phase 2 (streaming summary) inside `compact_messages_stream`. After Phase 1 commits new rows via `add_memory`, embed the newly-created rows, compare each against every other memory in the session via cosine similarity, drop new ones above the threshold, persist embeddings on the kept rows, and emit a debug SSE event describing what was kept and dropped.

## Locked-in decisions

1. Persist embeddings on the row. Add nullable `embedding: list[float] | None` JSON column to `ChatMemory`. `add_memory` writes the row without an embedding; embedding is computed during compaction.
2. Threshold is a hardcoded module constant in the new compaction module: `MEMORY_DEDUP_COSINE_THRESHOLD = 0.92` (cosine similarity; drop new memory when similarity ≥ threshold).
3. Dedup scope: each new memory is compared against all other session memories — both pre-existing rows (which may already have embeddings) and other-this-run new rows.
4. Discard the younger (new) memory; existing memories are authoritative.
5. No embedding server configured → silent skip. Log at DEBUG, no SSE error event, summarization continues. The `memory_compaction` SSE event is still emitted with `skipped=True`.
6. Hook placement: between Phase 1 and Phase 2 in `summarization_service.compact_messages_stream` — immediately before `yield _sse("phase", {"phase": "summarization"})`.
7. New SSE event type `memory_compaction`, Editor+ visibility, payload includes kept and dropped lists.
8. `add_memory_impl` (or its wrapping closure inside `compact_messages_stream`) must expose the created memory row id to the compaction step. The LLM-facing return string remains exactly `"Memory saved."`.

## Files involved

### Modify

- `backend/app/models/chat_memory.py` — add `embedding` JSON column.
- `backend/app/db/chats.py` — add `update_memory_embeddings(...)` and `delete_memories(...)` batch helpers.
- `backend/app/services/chat_tools.py` — surface created memory id from `add_memory_impl` so the summarization wrapper can capture it (LLM-facing string unchanged).
- `backend/app/services/summarization_service.py` — between Phase 1 and Phase 2: invoke compaction, emit `memory_compaction` SSE, swallow errors as skipped event.
- `backend/app/services/db_import_export.py` — round-trip `embedding` in `_chat_memory_to_dict` / `_dict_to_chat_memory`; absent key imports as `None`.

### Create

- `backend/app/services/memory_compaction.py` — `compact_new_memories(...)` plus the `MemoryCompactionResult` Pydantic model and module-level `MEMORY_DEDUP_COSINE_THRESHOLD`.
- `backend/tests/test_memory_dedup.py` — unit tests for the compaction routine and import/export round-trip (path subject to confirmation in `plan.md`).

## External references

- Embedding API: `backend/app/services/embedding.py` — `embed_texts(texts) -> list[list[float]]`, `is_embedding_configured() -> bool`, `EmbeddingNotConfiguredError`. No existing single-text helper, no existing cosine helper — this feature introduces the cosine helper inside `memory_compaction.py`.
- Embedding server gate: `db.llm_servers.get_embedding_server()` — already used elsewhere with swallow-and-degrade.
- Snowflake IDs: `app/services/snowflake.generate_id()`.
- Layer rule reminder: any session/exec stays inside `app/db/`. The new batch UPDATE/DELETE helpers belong in `db/chats.py`.

## Constraints / facts

- SQLite has no native vector type. Store the embedding as a SQLModel JSON column (`sa_column=Column(JSON)`); the field type is `list[float] | None`. JSONL import/export already round-trips JSON-serializable lists, so the only additional work is including the key in the to/from dict helpers.
- Old export files predate the new column. Imports without the `embedding` key must populate `None` (do not error out).
- `MAX_MEMORIES_PER_COMPACT = 5` cap on Phase 1 already exists (`_capped_add_memory`) — compaction operates on the at-most-5 rows added this run.
- The `saved_memories: list[str]` accumulator in the existing wrapper currently only stores the content string; this run also needs the row id (closure captures id alongside content, or a parallel `saved_memory_ids: list[int]` list).
- SSE visibility filtering is enforced at the writer layer by `caller_role`. Adding the new event row to the protocol table in `quick-reference.md` is part of the architect's `outcome.md`, not this code change.
- Dedup is in-Python over at most a few hundred memories per session; pure-Python cosine is fine — no LanceDB involvement.

## Out of scope (forwarded into plan.md)

- Threshold UI / pipeline config knob.
- Backfill of embeddings outside the compaction path. (Old rows get embeddings lazily — only when a future compaction in the same session embeds them as part of the "all other session memories" comparison set.)
- Cross-session / cross-user dedup.
- Cosine on the LanceDB side.
- `get_memory` tool changes.
- Frontend rendering of the new SSE event (debug panel surface is a follow-up).
