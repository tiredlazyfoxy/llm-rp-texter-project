# Feature 015 — background_retune

| Step | File                              | Status  | Verifier | Date |
|------|-----------------------------------|---------|----------|------|
| 001  | `001.session_wide_retune_core.md` | done    | PASS     | 2026-07-03 |
| 002  | `002.retune_task_registry.md`     | done    | PASS     | 2026-07-03 |
| 003  | `003.accept_fire_and_forget.md`   | pending | —        | —    |
| 004  | `004.retune_rest_api.md`          | pending | —        | —    |
| 005  | `005.frontend_transport_polling.md` | pending | —      | —    |
| 006  | `006.frontend_ui_gear_panel.md`   | pending | —        | —    |

## Files Changed

### Step 001 — Session-wide feedback + retune core
- `backend/app/db/generation_feedback.py` — added `list_by_session` DAL (all turns, created_at asc)
- `backend/app/services/retune_service.py` — `retune_session` core reads session-wide rejects, no emitter/turn-gate
- `backend/app/services/prompts/retune_prompt.py` — reworded prose/docstring to session-wide evidence; CHANGELOG entry

### Step 002 — Background task registry + lifecycle
- `backend/app/services/retune_tasks.py` — filled skeleton bodies: per-session `_registry`/`_locks`, lazy `_get_lock`, cancel-and-await-teardown `start` (fire-and-forget), detached `_run` (module-attr seam to `retune_service.retune_session`, None→0/absent→"" reconciliation, swallow cancel/log-swallow errors, self-clear guarded by identity), `stop` (cancel, no restart), sync `status` snapshot

## Skeleton

### Step 002 — frozen interface (2026-07-03)
- `backend/app/services/retune_tasks.py` — `@dataclass RetuneJob(task: asyncio.Task[None], running: bool, started_at: datetime)` — new (internal job record)
- `backend/app/services/retune_tasks.py` — `class RetuneStatus(TypedDict): running: bool; started_at: datetime | None` — new (status snapshot)
- `backend/app/services/retune_tasks.py` — `_registry: dict[int, RetuneJob] = {}` — new (per-session job registry)
- `backend/app/services/retune_tasks.py` — `_locks: dict[int, asyncio.Lock] = {}` — new (per-session lock map)
- `backend/app/services/retune_tasks.py` — `def _get_lock(session_id: int) -> asyncio.Lock` — new (lazy lock accessor)
- `backend/app/services/retune_tasks.py` — `async def start(session_id: int, user_id: int, world_id: int, model_id: str | None, turn_number: int | None) -> None` — new
- `backend/app/services/retune_tasks.py` — `async def _run(session_id: int, user_id: int, world_id: int, model_id: str | None, turn_number: int | None) -> None` — new (detached runner)
- `backend/app/services/retune_tasks.py` — `async def stop(session_id: int) -> None` — new
- `backend/app/services/retune_tasks.py` — `def status(session_id: int) -> RetuneStatus` — new (sync; reads registry only)
- Caller-compile edits (out of Source-files scope): None.

**Seam:** the runner reaches the core via module attribute `retune_service.retune_session` (module imported as `from app.services import retune_service`), NOT a direct symbol import — tests patch `app.services.retune_service.retune_session`.

**Signature reconciliation (binding decision for test-coder + coder):** step-001 core is `retune_session(session_id: int, user_id: int, world_id: int, turn_number: int, accepted_content: str, model_id: str | None) -> None`. `start(...)` omits `accepted_content` and allows `turn_number=None`. The runner maps: `turn_number` `None` → `0` passed to core (prompt/logging-only, never gates); no `accepted_content` at the `start` boundary → `""` passed to core (session-wide retune reads all reject rows; accepted turn text is not part of the background contract). `status(...)` is a plain `def` (registry read needs no `await`).

## Tests

### Step 002 — tests (2026-07-03)
- `backend/tests/services/test_retune_tasks.py` — covers DoD-1..DoD-7 — drives the
  registry with a controllable fake core patched at
  `app.services.retune_service.retune_session` (blocks on an `asyncio.Event`).
  - DoD-1: `test_status_running_then_idle_after_completion__DoD1` — running→idle;
    also asserts frozen reconciliation (turn_number None→0, accepted_content→"").
  - DoD-2: `test_second_start_cancels_first_single_live_job__DoD2` — one live job.
  - DoD-3: `test_restart_uses_latest_arguments__DoD3` — newest signal reaches core.
  - DoD-4: `test_stop_cancels_and_no_replacement__DoD4` — cancel, idle, no restart.
  - DoD-5: `test_two_sessions_run_independently__DoD5` — per-session independence.
  - DoD-6: `test_runner_success_path_clears_registry__DoD6`,
    `test_runner_swallows_cancellation_and_clears_registry__DoD6`,
    `test_runner_swallows_core_exception_and_clears_registry__DoD6` — all three
    completion paths swallow + clear the registry entry.
  - DoD-7: `test_start_returns_without_awaiting_core__DoD7` — non-blocking schedule.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓

## Notes & Issues

_populated by the coder when worth saying_
