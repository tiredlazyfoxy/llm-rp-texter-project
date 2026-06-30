# Fast feature 002 — memory_dedup_inline — context

## What this is

Inline cosine deduplication on every `add_memory` call. Embeds the candidate
content, compares against all existing session memories, and silently skips the
insert when a near-duplicate (cosine >= 0.85) already exists. Otherwise inserts
the row with its freshly-computed embedding stored at write time.

This is the follow-up to fast/001 (`memory_dedup`), which added post-extraction
**batch** compaction (threshold 0.92) inside the summarization pass. Batch
compaction is being **kept unchanged** as a redundant safety net; this feature
adds a second, earlier guard that covers the dominant duplicate source.

## Why fast/001 wasn't enough (root causes, locked)

1. The in-game `add_memory` tool is never deduped. `chat_tools.py` binds the
   gameplay tool as `add_memory_impl(session_id, content)` with no dedup.
   `compact_new_memories` only runs inside a summarization pass
   (`summarization_service.py` ~line 296) and only over rows added in *that*
   pass. Every memory the LLM writes during normal play accumulates with zero
   dedup — the dominant path.
2. Only "new this run" rows are deletion candidates in batch compaction —
   pre-existing near-duplicates are immortal peers, never collapsed.
3. 0.92 is too strict — real paraphrases embed in the 0.80–0.90 band and survive.

## Fix shape (user-approved, locked)

Dedup INLINE inside `add_memory_impl` so it covers **every** caller (gameplay +
summarization extraction) and compares against **all** existing session
memories. Threshold = 0.85 (a new constant, distinct from the batch 0.92).

## Files involved

- `backend/app/services/memory_compaction.py` — home of the existing batch
  compaction; gains the inline constant, `InlineDedupResult` model, and
  `find_duplicate_memory`. Reuses its `_cosine`, `is_embedding_configured`,
  `embed_texts`.
- `backend/app/services/chat_tools.py` — `add_memory_impl` is the single
  choke point every `add_memory` flows through.
- `backend/app/db/chats.py` — existing helpers `list_memories(session_id)`
  (full rows incl. embedding), `update_memory_embeddings(updates)`,
  `create_memory(memory)`. No new db helpers needed.
- `backend/tests/services/test_memory_dedup.py` — existing batch-compaction
  test, the mocking-style reference for the new test file.

## Feature-wide facts / constraints

- **No DB schema change.** The `embedding` column already exists on
  `ChatMemory` (added in fast/001) and `db_import_export.py` already
  round-trips it.
- **Layer separation** — all session/exec stays in `app/db/`. The service
  reuses `list_memories` / `update_memory_embeddings` / `create_memory`; it
  never opens a session itself.
- **LLM-facing surface is frozen** — `add_memory` keeps the same tool schema
  and always returns the literal string `"Memory saved."`, duplicate or not.
- **Inline dedup is silent** — DEBUG-logged only. No new SSE event, no
  frontend change.
- **Both guards coexist** — the 0.92 batch compaction
  (`compact_new_memories`, the summarization hook, the `memory_compaction` SSE
  event) is left fully intact.
- Embedding I/O is one batch `embed_texts` round-trip per call: the candidate
  content plus any existing rows missing an embedding (lazy backfill).
- Tests mock embeddings: monkeypatch `memory_compaction.is_embedding_configured`
  and `memory_compaction.embed_texts` to return hand-crafted vectors, mirroring
  `backend/tests/services/test_memory_dedup.py`.

## Build & test

- Backend tests: `cd backend && .venv/Scripts/python -m pytest`
