# Fast feature 002 — memory_dedup_inline — outcome

Doc changes for the architect to apply to `docs/architecture/` after this lands.

## `docs/architecture/quick-reference.md`

- **Section:** Chat Tools — the `add_memory(content)` bullet.
  **Change:** Note that `add_memory` now runs inline cosine dedup at threshold
  0.85 against all existing session memories before persisting. Near-duplicates
  (cosine >= 0.85) are silently not persisted while the LLM still receives
  exactly `"Memory saved."`. The row's embedding is computed and stored at write
  time, no longer deferred to compaction.
  **Reason:** The tool's persistence behavior and the timing of embedding
  computation changed.

- **Section:** Summarization / `chat_memories` row.
  **Change:** Note that embeddings are now populated at `add_memory` write time
  whenever an embedding server is configured, so the batch compaction's lazy
  embedding backfill rarely fires. The 0.92 batch compaction step is retained
  unchanged as a redundant safety net (now in addition to the inline 0.85
  guard).
  **Reason:** Keep the documented memory flow accurate now that there are two
  dedup guards at different thresholds.

## Not changed

- No SSE protocol change — inline dedup adds no new event; it is silent and
  DEBUG-logged only.
- No frontend doc change.
- No DB-model / import-export doc change — the `embedding` column already
  existed (fast/001).

## Observations

_populated by the coder when implementation lands_
