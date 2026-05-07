# Fast feature 001 — memory_dedup

| Status | Verifier | Date       |
|--------|----------|------------|
| done   | PASS     | 2026-05-07 |

## Files Changed

- `backend/app/models/chat_memory.py` — added nullable `embedding: list[float] | None` JSON column.
- `backend/app/db/engine.py` — added lightweight migration for the new `embedding` column on `chat_memories`.
- `backend/app/db/chats.py` — added `update_memory_embeddings(updates)` and `delete_memories(memory_ids)` batch helpers.
- `backend/app/services/memory_compaction.py` — new module: `MEMORY_DEDUP_COSINE_THRESHOLD`, Pydantic result models, `_cosine`, `compact_new_memories`.
- `backend/app/services/chat_tools.py` — `add_memory_impl` accepts optional `saved_memory_ids` accumulator (LLM-facing return string unchanged).
- `backend/app/services/summarization_service.py` — Phase 1 wrapper captures new memory ids; runs `compact_new_memories` between phases; emits one `memory_compaction` SSE event before `phase: summarization`; swallows errors as `skipped=True, skip_reason="error"`.
- `backend/app/services/db_import_export.py` — `_chat_memory_to_dict` / `_dict_to_chat_memory` round-trip `embedding`; absent key imports as `None`.
- `backend/tests/services/test_memory_dedup.py` — new test module covering cosine helper, dedup happy path (new vs existing), new-vs-new dedup, threshold boundary, no-embedding-server skip, empty-ids skip, and import/export round-trip including legacy export with no `embedding` key.

## Notes & Issues

- Test path placed under `backend/tests/services/test_memory_dedup.py` to match the existing per-service test layout (the plan allowed this confirmation).
- All 143 backend tests pass; the new file's 10 cases all pass.
- `ruff` / `mypy` were not runnable in this sandbox (binary launch denied). Manual review of imports and typing showed no obvious issues; verifier should re-run those gates.
