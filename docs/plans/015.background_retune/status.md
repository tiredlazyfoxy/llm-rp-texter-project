# Feature 015 — background_retune

| Step | File                              | Status  | Verifier | Date |
|------|-----------------------------------|---------|----------|------|
| 001  | `001.session_wide_retune_core.md` | done    | PASS     | 2026-07-03 |
| 002  | `002.retune_task_registry.md`     | done    | PASS     | 2026-07-03 |
| 003  | `003.accept_fire_and_forget.md`   | done    | PASS     | 2026-07-03 |
| 004  | `004.retune_rest_api.md`          | done    | PASS     | 2026-07-03 |
| 005  | `005.frontend_transport_polling.md` | done    | PASS     | 2026-07-03 |
| 006  | `006.frontend_ui_gear_panel.md`   | done    | PASS     | 2026-07-03 |

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

### Step 004 — Retune REST API (trigger / stop / status)
- `backend/app/services/tuning_service.py` — filled `trigger_retune`/`stop_retune`/`get_retune_status`; added `_load_owned_chat` (404-only ownership) + `_build_status` (shared status view: sync `retune_tasks.status` + profile read, None→empty strings, `world_id` stringified)
- `backend/app/models/schemas/chat.py` — `RetuneStatusResponse` schema (skeleton-provided; unchanged)
- `backend/app/routes/chat.py` — three retune routes (skeleton-provided; unchanged)

### Step 005 — Frontend transport + polling
- `frontend/src/user/pages/chatPageState.ts` — filled 5 retune actions (`startRetunePolling` idempotent 3s `setInterval` loop with running->idle edge detection + profile refresh, `stopRetunePolling`, `triggerRetuneNow`, `stopRetune`, `clearRetuneBlink`); added `pollRetuneStatus` helper + `RETUNE_POLL_INTERVAL_MS`; cleaned stale `tuning_update` comment
- `frontend/src/user/pages/ChatViewPage.tsx` — wired `startRetunePolling(state)` into the chat-open `useEffect` (mount side of the existing `dispose()`/`stopRetunePolling` teardown), per brief instruction

### Step 006 — Frontend UI: gear blink + panel running-state
- `frontend/src/user/pages/ChatViewPage.tsx` — added `Indicator` to Mantine import + `clearRetuneBlink` import; wrapped the settings-gear `ActionIcon` in a `processing` `Indicator` (shown when `state.retuneJustFinished`); gear `onClick` now calls `clearRetuneBlink(state)` before `setSettingsOpen(true)`
- `frontend/src/user/components/chats/ChatSettingsPanel.tsx` — added `Loader` import + `stopRetune`/`triggerRetuneNow` imports; tuning block now branches on `state.retuneRunning`: running → grayed/disabled textareas + `Loader` line + red Stop button (Save/Revert hidden); idle → editable textareas + Save/Revert + new "Retune now" button; post-retune reseed relies on the existing profile-driven `useEffect` (step-005 poll replaces `tuningProfile`)

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

### Step 004 — frozen interface (2026-07-03)
Schema — `backend/app/models/schemas/chat.py`:
- `class RetuneStatusResponse(BaseModel): running: bool; plan_tuning: str; tone_tuning: str; world_id: str` — new. `world_id` serialized as string (house style). `started_at` deliberately OMITTED — DoD strictly requires only these four fields and the running→idle edge is carried by `running`; kept minimal.

Service — `backend/app/services/tuning_service.py` (bodies `raise NotImplementedError`):
- `async def trigger_retune(chat_id: int, user_id: int) -> RetuneStatusResponse` — new
- `async def stop_retune(chat_id: int, user_id: int) -> RetuneStatusResponse` — new
- `async def get_retune_status(chat_id: int, user_id: int) -> RetuneStatusResponse` — new
- New module imports added (unused until coder fills bodies): `from fastapi import HTTPException, status`, `from app.db import chats as chats_db`, `from app.services import retune_tasks`, plus `RetuneStatusResponse` on the schema import.

Routes — `backend/app/routes/chat.py` (thin; `int(chat_id)` cast, `caller.id`; `_require_player` auth dep; `response_model=RetuneStatusResponse`):
- `POST /{chat_id}/retune` → `trigger_retune(chat_id, caller)` → `tuning_service.trigger_retune(int(chat_id), caller.id)` — new
- `POST /{chat_id}/retune/stop` → `stop_retune(chat_id, caller)` → `tuning_service.stop_retune(int(chat_id), caller.id)` — new
- `GET /{chat_id}/retune/status` → `get_retune_status(chat_id, caller)` → `tuning_service.get_retune_status(int(chat_id), caller.id)` — new
- Import edit: added `RetuneStatusResponse` to the `app.models.schemas.chat` import block.
- Caller-compile edits (out of Source-files scope): None.

**Binding decisions (frozen — coder must honor, test-coder binds to):**
- **session_id = chat.id** — `ChatSession` has NO `session_id` field; the record's own `id: int` IS the session id. Registry `start`/`stop`/`status` receive `chat.id`.
- **model_id = chat.text_model_id** (`str | None`) — same accessor the accept path uses.
- **world_id = chat.world_id** (`int`) — stringified in the response.
- **Ownership = 404-only.** `chat = await chats_db.get_session_by_id(chat_id)`; `if chat is None or chat.user_id != user_id: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")`. There is NO 403 path (step DoD said "404/403 per convention"; actual chat-route convention is uniform 404 — froze 404).
- **Manual trigger passes `turn_number=None`** to `retune_tasks.start(...)` — ignores the D2 gate (manual button always fires).
- **`retune_tasks.status(chat.id)` is SYNC** — read without `await`; the async `start`/`stop` are awaited.
- **All three endpoints return `RetuneStatusResponse`** (uniform status shape) so the frontend polls one shape; profile read via `await tuning_profiles_db.get(user_id, chat.world_id)` (None → empty strings, mirroring `get_profile`). Datetimes (if ever added) would be `.isoformat()`'d in the service; no schema-level serializer.

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

### Step 004 — tests (2026-07-03)
- `backend/tests/routes/test_retune_api.py` — covers DoD-1..DoD-5 — retune
  trigger/stop/status REST endpoints reached through the real FastAPI app
  (`http_client`) with an authenticated player (`player_user`); chats persisted
  via `db/chats` (session_id == chat.id), profiles seeded via `db/tuning_profiles`.
  DoD-1/DoD-2 drive the real `retune_tasks` registry with a blocking fake core
  patched at `app.services.retune_service.retune_session`; DoD-5 spies the
  scheduler at `app.services.retune_tasks.start`.
  - DoD-1: `test_trigger_starts_background_job_and_returns_status__DoD1` — POST
    /retune schedules a live job (registry running=True), returns a valid
    RetuneStatusResponse (200) whose `running` reflects the live job.
  - DoD-2: `test_stop_cancels_running_job_then_status_idle__DoD2` — POST
    /retune/stop cancels the running job; subsequent GET /status reports
    running=false.
  - DoD-3: `test_status_returns_profile_values_and_string_world_id__DoD3` — GET
    /status surfaces the seeded (user, world) profile's plan_tuning/tone_tuning
    with running=false and world_id serialized as a string.
  - DoD-4: `test_non_owner_rejected_404__DoD4` (trigger/stop/status parametrize)
    — a non-owner player gets 404 "Chat not found" on all three endpoints
    (404-only; no 403 path).
  - DoD-5: `test_manual_trigger_ignores_turn_gate_turn_number_none__DoD5` — with
    zero session rejects the manual trigger still calls `retune_tasks.start`
    once with `turn_number=None` and session/user/world/model bindings from the
    chat (session_id==chat.id, model_id==chat.text_model_id, world_id==chat.world_id).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 [manual/live, no test]

## Notes & Issues

_populated by the coder when worth saying_
