# Feature 015 — background_retune

## Goal & scope

Rework the feature 014 "chat_preference_tuning" retune mechanism so it runs as a
**background, session-scoped, controllable job** instead of an inline blocking
call on accept. Concretely, retune must:

1. Run in the **background** after every accept (explicit variant pick AND
   implicit keep-and-continue), **non-blocking** — accept never waits on the LLM.
2. Use **all tries across the whole session** as LLM evidence, not just the
   accepted turn's tries.
3. On finish: the settings UI tuning field updates and the settings gear icon
   blinks.
4. A manual **"Retune now"** button in the settings panel starts the same
   background process for the current session.
5. While a background retune runs: the tuning field is grayed/disabled with a
   spinner/icon.
6. A **Stop** button cancels the running background process; it can be run again
   for a specific session.
7. **Never two background retunes in parallel for the same session.**

This supersedes the inline on-accept retune and the editor-only `tuning_update`
SSE event delivered in feature 014.

## Locked design decisions (do NOT re-litigate)

- **D1 Transport = polling.** No push/SSE for retune status. Session-scoped REST:
  a trigger endpoint, a stop endpoint, and a status endpoint. The frontend polls
  status while a chat is open. This **replaces** the old `tuning_update` SSE event
  entirely.
- **D2 Auto-trigger gate = accepted turn had ≥1 reject.** A clean first-try
  accept never auto-triggers (unchanged gate). When it fires, the retune
  aggregates ALL session feedback (every reject across all turns) as LLM context —
  not just the accepted turn. The manual "Retune now" button fires regardless of
  the gate (still session-wide); with zero session rejects it is a fast no-op.
- **D3 Collision = cancel-and-restart.** If a retune is already running for the
  session and a new trigger arrives (auto-accept OR manual), cancel the in-flight
  job and start a fresh one with the latest signal. This guarantees ≤1 running per
  session (req 7). The Stop button (req 6) cancels **without** restart.
- **D4 Scope = chain mode only.** Simple/agentic untouched (simple mode writes no
  reject rows, so it has no retune signal). Manual "Retune now" surfaces only in
  chain mode. Matches feature 014's chain-only scope.

## Deployment fact that unblocks the design

Backend runs a **single uvicorn process** (prod: `uvicorn app.main:app` on :8085,
no `--workers`; dev: `--reload`). Therefore an **in-memory per-session task
registry is safe** — no DB-backed status column, no cross-worker coordination. If
the server restarts mid-retune, status resets to idle (acceptable; a retune is
cheap to re-trigger). `db/engine.py get_standalone_session()` creates a fresh
`AsyncSession` per DAL call, so DB access from a detached asyncio task is already
safe. **No new persistent table is needed** — status lives only in the in-memory
registry; `ChatTuningProfile` / `ChatGenerationFeedback` already exist, so
`db/engine.py` model imports and `db_import_export.py TABLE_REGISTRY` do NOT
change.

## Feature-014 anchors this feature builds on

- **`retune_service.maybe_retune(...)`** (`services/retune_service.py:55`) — today
  self-gates on turn-scoped rejects via `feedback_db.list_by_turn(...)`, no-ops if
  `model_id is None`, partitions rejects by scope (`plan`/`null`→plan dim;
  `text`/`null`→tone dim), runs `_retune_dimension` per targeted dim (one non-tool
  LLM completion each via `get_llm_client_for_model(model_id)`), upserts via
  `tuning_profiles_db.upsert(profile)`, then emits `tuning_update` if an emitter is
  present. `RetuneEmitter = Callable[[str, dict[str, str]], Awaitable[None]]`
  (`retune_service.py:30`).
- **`chat_service._record_accept_and_retune(...)`** (`services/chat_service.py:561`)
  — writes one `verdict="approved"` `ChatGenerationFeedback` row via
  `feedback_db.create(...)`, then `await retune_service.maybe_retune(...)`. Callers:
  `chat_service.py:655` (`continue_chat`, explicit accept, emitter=None),
  `chain_generation_service.py:845` (auto-commit, emitter=`_emit`),
  `simple_generation_service.py:382` (auto-commit, emitter=None).
- **Chain auto-commit** (`chain_generation_service.py:826-856`) buffers editor-gated
  frames into `pending_frames` via `_emit` (appends `sse(name,payload)` when
  `caller_role != "player"`), calls `_record_accept_and_retune(..., emitter=_emit)`,
  then `for frame in pending_frames: yield frame`. The single `verdict="rejected"`
  reject-row write is at `chain_generation_service.py:953` during regenerate.
- **DB access layer**: `db/generation_feedback.py` exposes exactly `create(...)`
  (:9), `list_by_turn(session_id, turn_number)` (:18, created_at order),
  `delete_by_session(session_id)` (:29). **No `list_by_session` exists.**
  `db/tuning_profiles.py`: `get(user_id, world_id)` (:9), `upsert(profile)` (:19).
- **Prompts**: `services/prompts/retune_prompt.py` (5-section docstring, re-exported
  via `__init__.py`) builds the retune prompt; session-wide evidence may need a
  small builder tweak, kept in that file.
- **Frontend**: `frontend/src/user/pages/chatPageState.ts` (class `ChatPageState`,
  `makeAutoObservable` at :78) — tuning observables `tuningProfile` (:71),
  `streamCtrl` (:73), existing `stopGeneration(state)` (:545), tuning actions
  `applyTuningUpdate` (:699) / `loadTuningProfile` (:711) / `saveTuningProfile`
  (:727) / `revertTuningProfile` (:739); `onTuningUpdate` wired into stream handlers
  at :349/:421/:504/:612. `ChatViewPage.tsx` gear at :88-92, `settingsOpen` at :26,
  panel mount :105. `ChatSettingsPanel.tsx` — `observer` (:90), Drawer, gating
  `isEditor` (:102) && `isChainMode` (:103) → `showTuning` (:104), tuning block
  :204-237. `api/chat.ts` — `onTuningUpdate?` (:16), `case "tuning_update"`
  (:298-301). `api/tuningProfile.ts` — `getTuningProfile` (:4), `updateTuningProfile`
  (:8) via shared `request<T>`. Types: `types/tuningProfile.d.ts` (`TuningProfile`,
  `UpdateTuningProfile`); `types/chat.d.ts:155-159` (`TuningUpdate`).

## Conventions to honor (project-wide)

- **Layers**: `routes/` (HTTP only) → `services/` (business logic, no DB sessions)
  → `db/` (session-free namespace modules; all `AsyncSession` internal). No
  `session`/`select` outside `db/`. Import style:
  `from app.db import generation_feedback` then `await
  generation_feedback.list_by_session(...)`; `from app.services import
  retune_service`.
- **Models**: Pydantic `BaseModel` for all API request/response schemas; SQLModel
  for tables; `TypedDict` for internal passing. No free dicts, no `any`. IDs
  serialize as **strings**.
- **Snowflake IDs** assigned in the service layer:
  `from app.services import snowflake as snowflake_svc; snowflake_svc.generate_id()`.
- **Prompts** live one-file-per-prompt under `backend/app/services/prompts/` with
  the 5-section docstring, re-exported via `__init__.py`.
- **Frontend**: TS + React + MobX, `observer` on every component, no `useState`
  for reactive state (component-local UI edit buffers are the existing exception),
  page-state classes + free-function actions, all HTTP in `src/api/`, DTOs in
  `src/types/`, no runtime validation, no `any`.

## Build / test commands

- Backend tests: `cd backend && .venv/Scripts/python -m pytest`
- Frontend typecheck: `cd frontend && npx tsc --noEmit`
- Frontend build (typecheck + bundle): `cd frontend && npm run build`
- No backend static type-check; **no frontend test runner** — the only frontend
  gate is `npx tsc --noEmit`. Treat frontend behavior DoD as `[manual/live]` and
  the tsc pass as the single `[test]`-equivalent gate.

## Architecture pointers

- `docs/architecture/quick-reference.md` — condensed DB models, API endpoints, SSE
  protocol, placeholders. Read first for cross-cutting context.
- `docs/plans/014.chat_preference_tuning/context.md` — shared tuning background
  (tuning profile shapes, plan/tone dimensions, reject attribution).

## Step map / files touched across steps

| Step | Theme | Primary surface |
|------|-------|-----------------|
| 001 | Session-wide retune core | `db/generation_feedback.py` (+`list_by_session`), `services/retune_service.py`, `services/prompts/retune_prompt.py` |
| 002 | Background task registry | new `services/retune_tasks.py` |
| 003 | Accept → fire-and-forget | `services/chat_service.py`, `services/chain_generation_service.py`, `services/simple_generation_service.py`, `services/retune_service.py` (drop emitter) |
| 004 | Retune REST API | `routes/chat.py`, `services/tuning_service.py` (or `retune_service`), `models/schemas/chat.py` (response schema) |
| 005 | Frontend transport + polling | `api/tuningProfile.ts` (or new `api/retune.ts`), `types/*.d.ts`, `chatPageState.ts`, `api/chat.ts` |
| 006 | Frontend UI: gear blink + panel | `user/pages/ChatViewPage.tsx`, `user/components/chats/ChatSettingsPanel.tsx` |

Dependency order: 001 → 002 → 003(needs 002) → 004(needs 002) → 005(needs 004) →
006(needs 005).
