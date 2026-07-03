# Feature 015 — background_retune

| Step | File                              | Status  | Verifier | Date |
|------|-----------------------------------|---------|----------|------|
| 001  | `001.session_wide_retune_core.md` | done    | PASS     | 2026-07-03 |
| 002  | `002.retune_task_registry.md`     | done    | PASS     | 2026-07-03 |
| 003  | `003.accept_fire_and_forget.md`   | done    | PASS     | 2026-07-03 |
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

### Step 003 — Accept path fire-and-forget
- `backend/app/services/chat_service.py` — `_record_accept_and_retune`: keeps the `approved` feedback-row write, adds the turn-scoped D2 gate (`feedback_db.list_by_turn` → any `rejected`), fires-and-forgets `retune_tasks.start(...)`; removed inline `retune_service.retune_session` call + import
- `backend/app/services/chain_generation_service.py` — auto-commit calls emitter-free hook (skeleton already dropped `_emit`/`pending_frames`/flush); verified compiles
- `backend/app/services/simple_generation_service.py` — auto-commit calls emitter-free hook; verified compiles
- `backend/app/services/retune_service.py` — unchanged (already emitter-free since step 001)

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

### Step 003 — frozen interface (2026-07-03)
- `backend/app/services/chat_service.py` — `async def _record_accept_and_retune(session_id: int, user_id: int, chat: ChatSession, accepted_content: str, accepted_plan_json: str | None) -> None` — changed (was `(session_id: int, user_id: int, chat: ChatSession, accepted_content: str, accepted_plan_json: str | None, emitter: Any = None) -> None`) — dropped the vestigial `emitter` param. Body left as-is (feedback-row write + inline `retune_service.retune_session`); the D2 gate + fire-and-forget `retune_tasks.start` rewrite is the coder's.
- `backend/app/services/retune_service.py` — no change; already emitter-free (no `maybe_retune`, no `RetuneEmitter`, no `tuning_update`) since step 001. DoD-6 already satisfied at the interface level.
- Caller-compile edits (out of Source-files scope): None — all three call sites are inside the Source files.
  - `chat_service.py:continue_chat` — removed `emitter=None` argument.
  - `chain_generation_service.py` auto-commit — removed `emitter=_emit` argument plus the dead `pending_frames` list, `_emit` def, and `for frame in pending_frames: yield frame` flush loop (they only ever carried the removed `tuning_update`; `_emit` had zero call sites, so the flush yielded nothing).
  - `simple_generation_service.py` auto-commit — removed `emitter=None` argument.

**Note:** module imports still resolve `Any` and `sse` (used elsewhere in their files); any now-unused import is left as coder cleanup, not a compile blocker. `_record_accept_and_retune`'s body still performs the old inline retune — that is preserved existing behavior; the new gate/background behavior is unimplemented and belongs to the coder.

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

### Step 003 — tests (2026-07-03)
- `backend/tests/services/test_accept_fire_and_forget.py` — covers DoD-1..DoD-6 —
  drives `chat_service._record_accept_and_retune(...)` against the real test DB
  (feedback rows), patching the fire-and-forget seam `app.services.retune_tasks.start`
  and the inline core `app.services.retune_service.retune_session` (recorders).
  - DoD-1: `test_accept_delegates_to_background_seam_without_awaiting_llm__DoD1` —
    reject-present accept schedules `retune_tasks.start` and never awaits the inline
    retune LLM (`retune_session` recorder stays empty); `asyncio.wait_for` guards
    against a blocking regression.
  - DoD-2: `test_reject_present_schedules_background_retune_with_args__DoD2` — gate
    fires; `start` called once with session/user/world(chat)/model(chat)/turn(current_turn).
  - DoD-3: `test_clean_accept_schedules_nothing__DoD3` — no reject on the turn →
    `start` not called; approved row still written.
  - DoD-4: `test_approved_row_written_regardless_of_gate__DoD4` (clean + reject
    parametrize) — one `verdict="approved"` row snapshotting the accepted content.
  - DoD-5: `test_accept_hook_produces_no_tuning_update_frame__DoD5` — frozen hook has
    no `emitter` param and is a coroutine (not async-gen) → yields no SSE frame.
  - DoD-6: `test_retune_service_has_no_emitter_surface__DoD6` — no `RetuneEmitter`,
    no `maybe_retune`, no `emitter` param on `retune_session`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 [manual/live, no test]

## Notes & Issues

_populated by the coder when worth saying_
