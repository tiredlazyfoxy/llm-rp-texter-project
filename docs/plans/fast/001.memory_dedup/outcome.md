# Fast feature 001 — memory_dedup — outcome

Doc changes the architect should apply to `docs/architecture/` after this feature lands. Grouped by target file.

## `docs/architecture/quick-reference.md`

### DB models — Feature 002 `chat_memories` row

- **Section**: the `chat_memories` row description in the DB models / Feature 002 area.
- **Change**: append a mention of the new nullable `embedding` field — `list[float] | None`, stored as a JSON column. Note that it is written by the post-extraction compaction step (not by `add_memory`) and that absence is meaningful (row predates compaction or compaction was skipped because no embedding server is configured).
- **Reason**: persistence-layer surface changed; readers of the quick-reference should see the new field without diving into the model file.

### SSE Streaming Protocol table

- **Section**: the SSE event table.
- **Change**: add a row for the new `memory_compaction` event. Payload sketch: `{ kept: [{id, content}], dropped: [{id, content, duplicate_of_id, duplicate_of_content, similarity}], skipped: bool, skip_reason: str|null }`. When = "After Phase 1, before Phase 2 of compaction (one event per compaction run, including when skipped)". Visibility = "Editor+".
- **Reason**: every SSE event type belongs in this table; clients (debug panel, future tooling) consult it as the contract.

### Summarization (feature 002 step 004) section

- **Section**: the summarization / `compact_messages_stream` description.
- **Change**: extend the description with the post-extraction compaction step — between Phase 1 and Phase 2 the service computes embeddings for the newly-added memories (and any pre-existing ones that lack them), runs cosine dedup against every other session memory at threshold `MEMORY_DEDUP_COSINE_THRESHOLD = 0.92`, deletes the younger duplicates, persists embeddings on survivors, and emits the `memory_compaction` SSE event. Document the silent-skip behavior when no embedding server is configured (logged at DEBUG, SSE event still emitted with `skipped=True`, summarization continues).
- **Reason**: the compaction phase is now part of the documented summarization flow; without this update the doc misrepresents what happens between Phase 1 and Phase 2.

### Chat Tools — `add_memory(content)` bullet

- **Section**: the chat-tools list, `add_memory` bullet.
- **Change**: note that rows are stored without embeddings; embeddings are computed during the next compaction. The LLM-facing return string remains `"Memory saved."`.
- **Reason**: clarifies that the embedding is a side effect of compaction, not of the tool call, so future readers don't expect `add_memory` to embed inline.

## `docs/architecture/backend.md`

- **Section**: the summarization service description, if present.
- **Change**: only if the architect's review shows summarization is described in enough detail that the new compaction step would be conspicuously missing. Otherwise leave a "no change expected — confirm during finalization" note.
- **Reason**: the quick-reference is the canonical surface for streaming protocol and tool catalogs; duplicating into `backend.md` is only worthwhile if that file already covers the summarization flow at a similar depth.

## Frontend docs

- No changes. Debug panel rendering of the new SSE event is a follow-up; until then, the frontend treats `memory_compaction` as an unknown debug event and ignores it.

## Observations

_(empty — the coder fills this in if anything surprised them during implementation)_
