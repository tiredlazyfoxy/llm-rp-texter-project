# Feature 014 — chat_preference_tuning

| Step | File                       | Status  | Verifier | Date |
|------|----------------------------|---------|----------|------|
| 001  | `001.data_layer.md`        | done    | PASS     | 2026-06-30 |
| 002  | `002.tuning_injection.md`  | done    | PASS     | 2026-06-30 |
| 003  | `003.reject_attribution.md`| done    | PASS     | 2026-06-30 |
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

### Step 003 — Reject attribution + scoped regenerate
- `backend/app/services/chain_generation_service.py` — added `generation_feedback`/`ChatGenerationFeedback` imports; `regenerate_chain_response` now writes one `verdict="rejected"` feedback row (scope/comment/content+plan snapshots) before discarding the active assistant message, then branches on scope: `scope="text"` deserializes the discarded `generation_plan` into `GenerationPlanOutput` and runs writer-only via new `_run_chain_generation(writer_only=True, prior_plan=...)` params (seeds `all_planning_contexts` from the prior plan, skips tool stages); `scope in {"plan", None}` unchanged.
- `backend/app/models/schemas/chat.py` — `RegenerateRequest.scope`/`.comment` (skeleton-frozen, verified).
- `backend/app/routes/chat.py` — regenerate route forwards `scope`/`comment` (skeleton-wired, verified).
- `backend/app/services/chat_agent_service.py` — `regenerate_response` forwards `scope`/`comment` to chain branch (skeleton-wired, verified).

## Notes & Issues

- Step 003: writer-only regen does NOT re-apply the prior plan's `stat_updates` to session stats (no tool stages run, so stats stay at the restored prev-turn snapshot). Spec lists only "feed prior plan to writer → finalize"; stat reapplication was out of scope. Flag if live behavior expects stat changes carried over.

## Tests

### Step 001 — tests (2026-06-30)
- `backend/tests/test_tuning_data_layer.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5
  - DoD-1: both tables built by `create_all` — insert a row via the db modules and read it back (`ChatTuningProfile`, `ChatGenerationFeedback`).
  - DoD-2: `tuning_profiles.get` → `None` for unknown pair; `upsert` then `get` returns stored `plan_tuning`/`tone_tuning`; second `upsert` updates in place (same id, new values).
  - DoD-3: `generation_feedback.create` + `list_by_turn` ordered by `created_at` asc (insert order ≠ created_at order, other-turn excluded); `delete_by_session` empties the turn.
  - DoD-4: JSONL `to_dict`→JSON→`from_dict` round-trip for a `ChatTuningProfile` row and `ChatGenerationFeedback` rows (null and populated `scope`/`comment`/`plan_snapshot`), all fields incl. timestamps intact.
  - DoD-5: `chats.delete_session` cascades — session's feedback rows gone after delete.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 [manual/live, no test], DoD-7 [manual/live, no test]

### Step 003 — tests (2026-06-30)
- `backend/tests/test_reject_attribution.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5.
  - DoD-1: `RegenerateRequest` schema — defaults None when omitted; round-trips `scope="text"`/`scope="plan"` + `comment`; explicit None still validates (with `turn_number`); JSON-body `model_validate` round-trip; rejects non-literal `scope` (ValidationError); annotation admits exactly `"plan"`/`"text"`/None.
  - DoD-2: `scope="text"` regen runs writer-only — no tool/planning LLM call (`max_loops!=20` calls empty) and the prior plan (`PRIOR_PLAN_MARKER`) reaches the writer's messages. (Red-gate fails until the writer-only branch is implemented — currently `NotImplementedError`.)
  - DoD-3: `scope="plan"` and `scope=None` (parametrized) run the full chain — both a tool-stage and a writer-stage LLM call occur.
  - DoD-4: a whole-chain regen writes exactly one `verdict="rejected"` feedback row (read via `generation_feedback.list_by_turn`) with the sent scope/comment, `content_snapshot` = discarded text, `plan_snapshot` = discarded `generation_plan`; cases: with comment+`scope="plan"`, null scope/comment, and null `plan_snapshot` when the discarded msg had no plan. (Red-gate fails until the feedback write is added.)
  - DoD-5: regen appends the discarded generation to variants and emits a `variants_update` SSE event — asserted on the whole-chain path and on the writer-only (`scope="text"`) path.
  - Harness (built fresh — no prior chain-run test existed): public `World` + chain `Pipeline` (one `tool` + one `writer` `PipelineStage`) + `ChatSession` at turn 1 + active user/assistant messages; LLM mocked at `chain_generation_service.get_llm_client_for_model` (writer stage detected by `max_loops==20`, prose via `on_delta`); generator driven to completion and SSE frames parsed for event names.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 [manual/live, no test]
