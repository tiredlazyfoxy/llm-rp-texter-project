# Fast feature 002 — memory_dedup_inline — plan

## Goal

Deduplicate memories inline at write time: on every `add_memory` call, embed the
candidate content, compare against all existing session memories, and skip the
insert when cosine >= 0.85 to any peer. Non-duplicates are inserted with their
computed embedding stored. The existing 0.92 batch compaction is kept untouched
as a safety net.

## Source files

- `backend/app/services/memory_compaction.py` — add the inline threshold
  constant, the `InlineDedupResult` model, and `find_duplicate_memory`; reuse
  the existing `_cosine`, `is_embedding_configured`, `embed_texts`. Leave
  `compact_new_memories` and `MEMORY_DEDUP_COSINE_THRESHOLD` (0.92) intact.
- `backend/app/services/chat_tools.py` — modify `add_memory_impl` to call
  `find_duplicate_memory` and branch on the result before creating a row.

## Test files

- `backend/tests/services/test_memory_dedup_inline.py` — new test file covering
  the `[test]`-tagged DoD items below, mirroring the mocking style of
  `backend/tests/services/test_memory_dedup.py`.

## Interface intent

### `memory_compaction.py`

- **`MEMORY_DEDUP_INLINE_COSINE_THRESHOLD`** — module-level float constant,
  value `0.85`. The inline-dedup cutoff; separate from and independent of the
  batch `MEMORY_DEDUP_COSINE_THRESHOLD` (0.92).

- **`InlineDedupResult`** — Pydantic `BaseModel` describing the outcome of an
  inline dedup check for one candidate. Fields:
  - `is_duplicate` — whether a near-duplicate peer was found at/above threshold.
  - `embedding` — the vector computed for the candidate content, or `None` when
    no embedding server is configured. The caller stores this on the new row
    when it inserts one.
  - `duplicate_of_id` — id of the highest-similarity existing peer (when
    duplicate), else `None`.
  - `similarity` — cosine to that highest-similarity peer (when duplicate),
    else `None`.

- **`find_duplicate_memory(session_id, content)`** — async. Decides whether
  `content` duplicates an existing memory in the session and computes its
  embedding. Responsibilities, in order:
  1. Gate on `await is_embedding_configured()`. If false, return immediately
     with `is_duplicate=False`, `embedding=None` — no DB load, no embed call.
  2. Load the comparison set via `list_memories(session_id)` (the candidate is
     not yet persisted, so there is no self-match to exclude).
  3. Embed the candidate content together with any existing rows that lack an
     embedding, in a single `embed_texts` round-trip where possible.
  4. Persist the freshly-computed embeddings for those backfilled existing rows
     via `update_memory_embeddings` (lazy backfill, so later calls are cheap).
  5. Cosine-compare the candidate vector against every existing row's vector via
     `_cosine`. Track the highest-similarity peer.
  6. If the max cosine `>= MEMORY_DEDUP_INLINE_COSINE_THRESHOLD`, return
     `is_duplicate=True` with that peer's id and similarity (and the candidate
     embedding). Otherwise return `is_duplicate=False` with the candidate
     embedding.
  - If no embedding server is configured at any point (including
    `EmbeddingNotConfiguredError` raised mid-flight), return `is_duplicate=False`,
    `embedding=None` so the caller inserts the row without dedup or embedding.

### `chat_tools.py`

- **`add_memory_impl`** — keep its current outward shape (same parameters
  including the optional `saved_memory_ids` collector used by the summarization
  wrapper; same `"Memory saved."` return). New internal flow:
  1. `dedup = await find_duplicate_memory(session_id, content)`.
  2. If `dedup.is_duplicate`: DEBUG-log the suppression, persist nothing, append
     nothing to `saved_memory_ids`, return `"Memory saved."`.
  3. Else: create the `ChatMemory` with `embedding` set to `dedup.embedding`,
     `create_memory(...)`, append the new id to `saved_memory_ids` when that
     collector was provided, return `"Memory saved."`.
  - No tool-schema change; the LLM-facing return string is `"Memory saved."` in
    both branches.

## Definition of done

- **DoD-1** `[test]` A candidate whose cosine to an existing session memory is
  `>= 0.85` is NOT persisted (session memory row count unchanged) and
  `add_memory_impl` returns exactly `"Memory saved."`; no id is appended to
  `saved_memory_ids`.
- **DoD-2** `[test]` A candidate whose cosine to every existing memory is
  `< 0.85` is persisted; the new row's stored `embedding` equals the vector
  computed for the candidate; the new id is appended to `saved_memory_ids`;
  return is `"Memory saved."`.
- **DoD-3** `[test]` Threshold is inclusive: a candidate at cosine exactly
  `0.85` is treated as a duplicate (suppressed); a `0.84` pair is kept. The
  comparison is `>=` against `MEMORY_DEDUP_INLINE_COSINE_THRESHOLD`.
- **DoD-4** `[test]` With `is_embedding_configured()` patched to `False`, the
  row is created with `embedding is None`, no candidate embed call is made, no
  exception is raised, and the return is `"Memory saved."`.
- **DoD-5** `[test]` First memory in an empty session: with an empty comparison
  set the candidate is never a duplicate; the row is created carrying its
  computed embedding.
- **DoD-6** `[test]` Lazy backfill: an existing row whose `embedding is None` is
  embedded and persisted during a `find_duplicate_memory` call and participates
  in the comparison.
- **DoD-7** `[manual/live]` Inline dedup logic lives inside `add_memory_impl`,
  so both gameplay and summarization-extraction `add_memory` calls are covered
  by the same path.
- **DoD-8** `[manual/live]` The existing 0.92 batch compaction
  (`compact_new_memories`, the summarization hook, the `memory_compaction` SSE
  event) is unchanged and still functions.
- **DoD-9** `[manual/live]` `add_memory`'s LLM-facing surface is unchanged: same
  tool schema, same `"Memory saved."` return string in every branch.
- **DoD-10** `[manual/live]` Backend test suite passes
  (`cd backend && .venv/Scripts/python -m pytest`).

## Out of scope

- Removing or modifying the 0.92 batch compaction (keep both guards).
- Any threshold UI or pipeline config knob.
- Cross-session / cross-user dedup.
- Retroactively collapsing pre-existing duplicate pairs (inline only prevents
  NEW duplicates).
- Real-embedding integration tests (mocked vectors only, per fast/001).
- Any frontend change; any new SSE event.
- DB schema or import/export changes (the `embedding` column already exists and
  round-trips).
