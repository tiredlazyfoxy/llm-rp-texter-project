# Fast feature 001 — memory_dedup — plan

## Goal

Phase 1 of summarization keeps emitting near-duplicate `add_memory` calls, and `chat_memories` accumulates redundant rows. Insert a between-phases compaction step that embeds the newly-added rows, cosine-compares each against every other session memory, deletes the new ones above threshold, persists the surviving embeddings, and emits a debug SSE event describing what was kept and dropped.

## Files to create or modify

- `backend/app/models/chat_memory.py` — add nullable `embedding` JSON column on `ChatMemory`.
- `backend/app/db/chats.py` — add session-free batch helpers `update_memory_embeddings(...)` and `delete_memories(...)`.
- `backend/app/services/memory_compaction.py` — **new module** holding `compact_new_memories(...)`, the `MemoryCompactionResult` / `MemoryRef` / `DroppedMemory` Pydantic models, the `MEMORY_DEDUP_COSINE_THRESHOLD = 0.92` constant, and an internal cosine helper.
- `backend/app/services/chat_tools.py` — surface the created memory id from `add_memory_impl` so the summarization wrapper can capture it; LLM-facing return string stays exactly `"Memory saved."`.
- `backend/app/services/summarization_service.py` — between Phase 1 and Phase 2 in `compact_messages_stream`, call `compact_new_memories(...)`, emit the `memory_compaction` SSE event, and swallow errors as a `skipped=True` event.
- `backend/app/services/db_import_export.py` — round-trip `embedding` in `_chat_memory_to_dict` / `_dict_to_chat_memory`; absent key imports as `None`.
- `backend/tests/test_memory_dedup.py` — **new test file** (path subject to confirmation against existing `backend/tests/` layout — coder picks the matching module location if tests live elsewhere).

## Signatures

### `chat_memory.py` — model field addition

```python
embedding: list[float] | None = Field(
    default=None,
    sa_column=Column(JSON, nullable=True),
)
```

### `db/chats.py` — new batch helpers

```python
async def update_memory_embeddings(
    updates: dict[int, list[float]],
) -> None:
    """Set `embedding` on the given memory ids in a single transaction."""

async def delete_memories(
    memory_ids: list[int],
) -> None:
    """Hard-delete `chat_memories` rows by id."""
```

Both follow the existing `db/chats.py` style: own the session, no `AsyncSession` leaks across the layer boundary.

### `services/memory_compaction.py` — new module

```python
MEMORY_DEDUP_COSINE_THRESHOLD: float = 0.92


class MemoryRef(BaseModel):
    id: int
    content: str


class DroppedMemory(BaseModel):
    id: int
    content: str
    duplicate_of_id: int
    duplicate_of_content: str
    similarity: float


class MemoryCompactionResult(BaseModel):
    kept: list[MemoryRef]
    dropped: list[DroppedMemory]
    skipped: bool = False
    skip_reason: str | None = None


async def compact_new_memories(
    chat_id: int,
    new_memory_ids: list[int],
) -> MemoryCompactionResult:
    """Embed the new rows, compare against every other session memory via cosine,
    delete the new ones above threshold, persist embeddings on the kept rows.
    Returns kept/dropped lists. Returns `skipped=True` (and writes nothing) when
    no embedding server is configured or when `new_memory_ids` is empty."""


def _cosine(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity. Returns 0.0 when either vector is zero-length
    or zero-norm."""
```

Behavioral notes (binding for the coder):

- Pre-existing memories without an embedding get embedded as part of the comparison set so they can be compared and so a later compaction reuses the cached vector. Their embeddings are persisted via `update_memory_embeddings`.
- Comparisons include both pre-existing rows and other-this-run new rows; the younger row loses ties.
- The "duplicate_of" recorded in `DroppedMemory` is the highest-similarity peer that survived the comparison.
- All embedding I/O is one batch call into `embedding.embed_texts`.
- Caller gates on `is_embedding_configured()`; the function itself also short-circuits to a `skipped` result if `EmbeddingNotConfiguredError` is raised mid-flight.

### `chat_tools.py` — `add_memory_impl` return shape

Pick the wrapper-side mechanism: `add_memory_impl` gains a parameter (or the closure captures a list) so the created `ChatMemory.id` is appended to a `saved_memory_ids: list[int]` collected by `compact_messages_stream`. The function still returns the literal string `"Memory saved."` to the LLM. No tool-schema change. Concretely, the existing `_capped_add_memory` wrapper inside `compact_messages_stream` keeps its current signature toward the LLM and additionally pushes the new row id into a sibling list owned by the wrapper closure.

### `summarization_service.py` — hook skeleton

Between Phase 1 and Phase 2, immediately before `yield _sse("phase", {"phase": "summarization"})`:

```python
# saved_memory_ids: list[int] populated by the add_memory wrapper during Phase 1
try:
    if saved_memory_ids and is_embedding_configured():
        result = await compact_new_memories(chat_id, saved_memory_ids)
    else:
        result = MemoryCompactionResult(
            kept=[],
            dropped=[],
            skipped=True,
            skip_reason="no_embedding_server" if saved_memory_ids else "no_new_memories",
        )
except Exception:
    logger.exception("memory compaction failed")
    result = MemoryCompactionResult(
        kept=[], dropped=[], skipped=True, skip_reason="error",
    )

yield _sse("memory_compaction", result.model_dump())
```

Coder owns final wording, logger choice, and exact placement of the import. The constraint is: exactly one `memory_compaction` event, after Phase 1's commit and before the `phase: summarization` event.

### SSE payload — `memory_compaction`

Event name: `memory_compaction`. Payload (JSON):

```jsonc
{
  "kept": [ { "id": <int>, "content": <string> } ],
  "dropped": [
    {
      "id": <int>,
      "content": <string>,
      "duplicate_of_id": <int>,
      "duplicate_of_content": <string>,
      "similarity": <float>
    }
  ],
  "skipped": <bool>,
  "skip_reason": <string|null>
}
```

Visibility: Editor+ (filtered by `caller_role` at the writer layer; no extra plumbing in this feature).

## Tests

Test file: `backend/tests/test_memory_dedup.py` (coder confirms by surveying the existing `backend/tests/` layout — if tests are organized by service/module, follow that convention and adjust the path).

Cases:

- **dedup happy path** — seed one existing memory in the session; during a compaction run, add one near-duplicate (cosine ≥ 0.92 vs. the existing). After `compact_new_memories`, the new row is deleted, the original is untouched, and the SSE event payload lists the new id under `dropped` with `duplicate_of_id` pointing at the original.
- **dedup new-vs-new** — no pre-existing memories; add two new memories within the same run whose embeddings have cosine ≥ threshold. The first stays, the second is dropped. Confirm via DB read and the SSE payload.
- **threshold boundary** — two memories with cosine just below 0.92 (e.g. 0.91). Both kept, `dropped` list empty.
- **no embedding server** — patch `is_embedding_configured()` to return `False`. The compaction step emits `memory_compaction` with `skipped=True` and `skip_reason="no_embedding_server"`, no rows are touched, no exception bubbles, and Phase 2 still proceeds.
- **import/export round-trip** — export a session with one memory carrying an embedding and one without; re-import into an empty DB; assert both rows round-trip with `embedding` preserved (`list[float]` and `None` respectively). Also import a fixture predating the column (no `embedding` key) and assert it loads with `embedding=None`.

## Definition of done

- `embedding` column lands on `ChatMemory` and round-trips through JSONL import/export, including `None` for old exports.
- `compact_messages_stream` emits exactly one `memory_compaction` SSE event between Phase 1 and Phase 2 when run; emits the same event with `skipped: true` when no embedding server is configured; never emits before Phase 1's commit and never after the Phase 2 `phase: summarization` event.
- Memories with cosine similarity ≥ `MEMORY_DEDUP_COSINE_THRESHOLD` (0.92) to any other session memory are deleted before Phase 2, and surviving memories are visible to subsequent `get_memory` calls.
- Errors inside the compaction step do not abort summarization — they are caught, logged, and reported via the SSE event with `skipped=True`.
- LLM-facing surface of `add_memory` is unchanged — still returns the literal string `"Memory saved."` and the tool schema is identical.
- `mypy`, `ruff`, and `pytest` all pass for the touched files.

## Out of scope

- Threshold UI / pipeline config knob.
- Backfill of embeddings outside the compaction path. (Old rows get embeddings lazily — only when a future compaction in the same session embeds them as part of the "all other session memories" comparison set.)
- Cross-session / cross-user dedup.
- Cosine on the LanceDB side.
- `get_memory` tool changes.
- Frontend rendering of the new SSE event (debug panel surface is a follow-up).
