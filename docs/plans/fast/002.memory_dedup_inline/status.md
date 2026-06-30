# Fast feature 002 — memory_dedup_inline

| Status | Verifier | Date       |
|--------|----------|------------|
| done   | PASS     | 2026-06-30 |

## Files Changed

- `backend/app/services/memory_compaction.py` — implemented `find_duplicate_memory` (inline cosine dedup at write time: gate, single embed batch with lazy backfill, persist backfilled embeddings, `>= 0.85` peer match)
- `backend/app/services/chat_tools.py` — wired `add_memory_impl` to call `find_duplicate_memory`; suppress near-duplicates, else insert row carrying the candidate embedding

## Skeleton

### Frozen interface (2026-06-30)
- `backend/app/services/memory_compaction.py` — `MEMORY_DEDUP_INLINE_COSINE_THRESHOLD: float = 0.85` — new (module constant, distinct from existing `MEMORY_DEDUP_COSINE_THRESHOLD = 0.92`)
- `backend/app/services/memory_compaction.py` — `class InlineDedupResult(BaseModel)` — new — fields: `is_duplicate: bool`, `embedding: list[float] | None = None`, `duplicate_of_id: int | None = None`, `similarity: float | None = None`
- `backend/app/services/memory_compaction.py` — `async def find_duplicate_memory(session_id: int, content: str) -> InlineDedupResult` — new (stub raises `NotImplementedError`)
- `backend/app/services/chat_tools.py` — `async def add_memory_impl(session_id: int, content: str, saved_memory_ids: list[int] | None = None) -> str` — unchanged (signature confirmed; no code edit made — internal flow is the coder's job)
- Caller-compile edits (out of Source-files scope): None.

## Tests

### Tests (2026-06-30)
- `backend/tests/services/test_memory_dedup_inline.py` — covers DoD-1..DoD-6 — inline cosine dedup at write time (suppress near-duplicate, keep distinct + store embedding, inclusive 0.85 threshold, no-server insert, empty-session first memory, lazy backfill)
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓ (two tests: at-threshold + below), DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 [manual/live, no test], DoD-8 [manual/live, no test], DoD-9 [manual/live, no test], DoD-10 [manual/live, no test]

## Notes & Issues

_populated by the coder when worth saying_
