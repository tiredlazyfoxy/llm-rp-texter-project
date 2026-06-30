# Feature 014 — chat_preference_tuning

| Step | File                       | Status  | Verifier | Date |
|------|----------------------------|---------|----------|------|
| 001  | `001.data_layer.md`        | done    | PASS     | 2026-06-30 |
| 002  | `002.tuning_injection.md`  | done    | PASS     | 2026-06-30 |
| 003  | `003.reject_attribution.md`| pending | —        | —    |
| 004  | `004.retune_service.md`    | pending | —        | —    |
| 005  | `005.profile_api_transport.md` | pending | —     | —    |
| 006  | `006.frontend_ui.md`       | pending | —        | —    |

## Files Changed

### Step 001 — Data layer
- `backend/app/db/tuning_profiles.py` — implemented `get`/`upsert` (session.merge pattern)
- `backend/app/db/generation_feedback.py` — implemented `create`/`list_by_turn` (created_at asc)/`delete_by_session`
- `backend/app/services/db_import_export.py` — implemented the two to_dict/from_dict serialization pairs
- `backend/app/models/chat_tuning_profile.py` — model (verified, already stubbed correctly)
- `backend/app/models/chat_generation_feedback.py` — model (verified, already stubbed correctly)
- `backend/app/models/schemas/chat.py` — `TuningProfileResponse`/`UpdateTuningProfileRequest` (verified, already complete)
- `backend/app/db/engine.py` — model imports + `delete_session` cascade (verified, already in place)
- `backend/app/db/chats.py` — `delete_session` feedback cascade (verified, already in place)

### Step 002 — Tuning injection
- `backend/app/services/chain_generation_service.py` — implemented `_load_tuning` (reads profile via `tuning_profiles` db module, returns `("", "")` when none); added top-level `tuning_profiles_db` import. `_build_placeholder_values` / stage threading / `_run_chain_generation` load were skeleton-wired and verified intact.
- `backend/app/services/prompts/placeholder_registry.py` — verified `PLAN_TUNING`/`TONE_TUNING` registry entries (no change needed).
- `backend/app/services/prompts/default_templates.py` — verified `{PLAN_TUNING}` (tool + director) and `{TONE_TUNING}` (writer) tokens read sensibly when empty (no change needed).

## Notes & Issues

_populated by the coder when worth saying_

## Tests

### Step 001 — tests (2026-06-30)
- `backend/tests/test_tuning_data_layer.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5
  - DoD-1: both tables built by `create_all` — insert a row via the db modules and read it back (`ChatTuningProfile`, `ChatGenerationFeedback`).
  - DoD-2: `tuning_profiles.get` → `None` for unknown pair; `upsert` then `get` returns stored `plan_tuning`/`tone_tuning`; second `upsert` updates in place (same id, new values).
  - DoD-3: `generation_feedback.create` + `list_by_turn` ordered by `created_at` asc (insert order ≠ created_at order, other-turn excluded); `delete_by_session` empties the turn.
  - DoD-4: JSONL `to_dict`→JSON→`from_dict` round-trip for a `ChatTuningProfile` row and `ChatGenerationFeedback` rows (null and populated `scope`/`comment`/`plan_snapshot`), all fields incl. timestamps intact.
  - DoD-5: `chats.delete_session` cascades — session's feedback rows gone after delete.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 [manual/live, no test], DoD-7 [manual/live, no test]
