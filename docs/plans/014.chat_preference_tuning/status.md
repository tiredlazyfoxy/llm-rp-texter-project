# Feature 014 — chat_preference_tuning

| Step | File                       | Status  | Verifier | Date |
|------|----------------------------|---------|----------|------|
| 001  | `001.data_layer.md`        | done    | PASS     | 2026-06-30 |
| 002  | `002.tuning_injection.md`  | done    | PASS     | 2026-06-30 |
| 003  | `003.reject_attribution.md`| done    | PASS     | 2026-06-30 |
| 004  | `004.retune_service.md`    | done    | PASS     | 2026-06-30 |
| 005  | `005.profile_api_transport.md` | done    | PASS     | 2026-06-30 |
| 006  | `006.frontend_ui.md`       | done    | PASS     | 2026-06-30 |

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

### Step 004 — Retune service + accept trigger
- `backend/app/services/prompts/retune_prompt.py` — implemented `build_retune_prompt` (plan vs. tone framing, reject/accept evidence assembly, output-only instruction; truncates snapshots)
- `backend/app/services/retune_service.py` — implemented `maybe_retune` (self-gates on zero rejected rows; partitions by scope with null-scope counting for both dims; non-streamed `client.chat(..., stream=False)` per targeted dimension; upsert create/update preserving untargeted dim + created_at; editor-only `tuning_update` emit when emitter present; `model_id is None` → no-op)
- `backend/app/services/prompts/__init__.py` — re-export verified (already present from skeleton; no change)
- `backend/app/services/chat_service.py` — accept hook verified (skeleton-wired `approved`-feedback write + `maybe_retune(..., emitter=None)`; behavior complete, no change)

### Step 005 — Profile API + frontend transport
- `backend/app/services/tuning_service.py` — implemented `get_profile` (defaults `TuningProfileResponse(id="", ...)` when no row, else `_to_response`) and `update_profile` (create with snowflake id when absent, else mutate plan/tone + bump `modified_at` preserving id/created_at; upsert; `datetime.now(timezone.utc)` matching retune_service)
- `backend/app/routes/chat.py` — GET/PUT tuning-profile endpoints (skeleton-wired, verified forward to service)
- `frontend/src/api/tuningProfile.ts` — GET/PUT profile client (skeleton-wired, verified real `request<T>` transport)
- `frontend/src/types/tuningProfile.d.ts` — `TuningProfile`/`UpdateTuningProfile` DTOs (skeleton-wired, verified)
- `frontend/src/types/chat.d.ts` — `RegenerateRequest` scope/comment + ambient `TuningUpdate` (skeleton-wired, verified)
- `frontend/src/api/chat.ts` — `onTuningUpdate` handler, `tuning_update` case (double-cast), regenerate scope/comment body (skeleton-wired, verified)

### Step 006 — Frontend UI: reject affordances + preferences panel
- `frontend/src/user/pages/chatPageState.ts` — filled the 6 frozen actions (`fastReject`/`rejectWithComment` via new shared `streamRegenerate` helper that forwards scope+comment; `applyTuningUpdate`, `loadTuningProfile`, `saveTuningProfile`, `revertTuningProfile`); wired `onTuningUpdate` into `sendMessage`/`regenerate`/`regenerateAtTurn`/`streamRegenerate` handler objects; `loadChat` now loads the tuning profile when the world resolves as chain mode
- `frontend/src/user/components/chats/MessageBubble.tsx` — chain-mode three reject affordances (fast plan / fast text / reject-with-comment) replacing the single regenerate; comment input renders the rejected generation's content (no new fetch); non-chain keeps plain regenerate; variant switcher + green accept untouched
- `frontend/src/user/components/chats/ChatInput.tsx` — bottom regenerate mirrors the same chain-mode three-affordance set + comment input showing the latest assistant content; non-chain keeps plain regenerate
- `frontend/src/user/components/chats/ChatSettingsPanel.tsx` — editor+/admin- and chain-gated preferences section (editable `plan_tuning`/`tone_tuning` Textareas, Save + Revert), seeded from `state.tuningProfile`, reseeded live on `tuning_update`; loads the profile when opened in chain mode if unloaded

## Skeleton

### Step 006 — frozen interface (2026-06-30)

Frontend (`frontend/`), all in `src/user/pages/chatPageState.ts`:

New MobX observables on class `ChatPageState` (field initializers, auto-picked by `makeAutoObservable`):
- `rejectComment = ""` — pending free-text for the "reject with comment" affordance.
- `rejectCommentOpen = false` — toggles the comment input.
- `tuningProfile: TuningProfile | null = null` — in-memory preference profile (plan_tuning / tone_tuning).
- Added `import type { TuningProfile, UpdateTuningProfile } from "../../types/tuningProfile";` (`TuningUpdate` is ambient, no import).

New free-function actions (stub bodies `throw new Error("not implemented: …")`; params marked used via `void` to satisfy `noUnusedParameters`):
- `export async function fastReject(state: ChatPageState, scope: "plan" | "text"): Promise<void>` — new (one-click, comment-less reject).
- `export async function rejectWithComment(state: ChatPageState): Promise<void>` — new (always `scope="plan"` + `state.rejectComment`, then clears/closes the input).
- `export function applyTuningUpdate(state: ChatPageState, data: TuningUpdate): void` — new (the `onTuningUpdate` SSE handler; overwrites `state.tuningProfile`).
- `export async function loadTuningProfile(state: ChatPageState, signal?: AbortSignal): Promise<void>` — new.
- `export async function saveTuningProfile(state: ChatPageState, body: UpdateTuningProfile, signal?: AbortSignal): Promise<void>` — new.
- `export async function revertTuningProfile(state: ChatPageState, signal?: AbortSignal): Promise<void>` — new (reload from server).

Components — no signature changes:
- `MessageBubble.tsx`, `ChatInput.tsx`, `ChatSettingsPanel.tsx` all already receive `state: ChatPageState` and read everything they need off it. No new props or exported helpers were needed, so these files are untouched. JSX affordances (three reject controls, comment input rendering the rejected content, the debug-gated preferences panel) are UI behavior left entirely for the coder.

Caller-compile edits (out of Source-files scope): None. (All additions are new exports/fields; no existing signature changed.)

Contract notes for downstream roles:
- Chain-mode detection signal (per harvested facts): `state.world?.generation_mode === "chain"`. Not re-frozen here — `world: WorldInfo | null` already exists on `ChatPageState`.
- `applyTuningUpdate` is exported so the coder can wire it into the inline SSE handler objects' `onTuningUpdate` slot (currently unconsumed in `chatApi.regenerateMessage`/`sendMessage` call sites).
- `saveTuningProfile` takes an explicit `UpdateTuningProfile` body (matches `updateTuningProfile` transport); the coder decides whether the panel holds local edit state or mutates `state.tuningProfile` directly.
- No frontend test runner exists; the only gate is `npx tsc --noEmit`, which passes clean with these stubs.

### Step 005 — frozen interface (2026-06-30)

Backend (`backend/`):
- `app/services/tuning_service.py` — `async def get_profile(user_id: int, world_id: int) -> TuningProfileResponse` — new (stub raises `NotImplementedError`)
- `app/services/tuning_service.py` — `async def update_profile(user_id: int, world_id: int, req: UpdateTuningProfileRequest) -> TuningProfileResponse` — new (stub raises `NotImplementedError`)
- `app/services/tuning_service.py` — `def _to_response(profile: ChatTuningProfile) -> TuningProfileResponse` — new helper (implemented; pure mapping, no behavior). `snowflake_svc` import is present for the coder's `update_profile` create path.
- `app/routes/chat.py` — `GET /api/chats/tuning-profile/{world_id}` → `get_tuning_profile(world_id: str, caller=Depends(_require_player)) -> TuningProfileResponse` — new; calls `tuning_service.get_profile(caller.id, int(world_id))`
- `app/routes/chat.py` — `PUT /api/chats/tuning-profile/{world_id}` → `update_tuning_profile(world_id: str, req: UpdateTuningProfileRequest, caller=Depends(_require_player)) -> TuningProfileResponse` — new; calls `tuning_service.update_profile(caller.id, int(world_id), req)`
- `app/routes/chat.py` — import block: added `TuningProfileResponse`, `UpdateTuningProfileRequest` from `app.models.schemas.chat`; added `from app.services import tuning_service` — new (schemas reused from step 001, not redefined)

Frontend (`frontend/`):
- `src/types/chat.d.ts` — `RegenerateRequest` — changed (was `{ turn_number?: number }`); now `{ turn_number?: number; scope?: "plan" | "text"; comment?: string }`
- `src/types/chat.d.ts` — `interface TuningUpdate { plan_tuning: string; tone_tuning: string; world_id: string }` — new (ambient, no `export`)
- `src/types/tuningProfile.d.ts` — `export interface TuningProfile { id: string; world_id: string; plan_tuning: string; tone_tuning: string }`; `export interface UpdateTuningProfile { plan_tuning: string; tone_tuning: string }` — new file
- `src/api/tuningProfile.ts` — `export async function getTuningProfile(worldId: string, signal?: AbortSignal): Promise<TuningProfile>`; `export async function updateTuningProfile(worldId: string, body: UpdateTuningProfile, signal?: AbortSignal): Promise<TuningProfile>` — new file (real `request<T>` transport wiring)
- `src/api/chat.ts` — `ChatSSEHandlers.onTuningUpdate?: (data: TuningUpdate) => void` — changed (added field)
- `src/api/chat.ts` — `regenerateMessage(chatId: string, handlers: ChatSSEHandlers, turnNumber?: number, scope?: "plan" | "text", comment?: string): AbortController` — changed (was `(chatId, handlers, turnNumber?)`); body typed `RegenerateRequest`, includes scope/comment when set
- `src/api/chat.ts` — `_streamChat` SSE switch: added `case "tuning_update"` → `handlers.onTuningUpdate?.(parsed as unknown as TuningUpdate)` — changed
- Caller-compile edits (out of Source-files scope): None. (`regenerateMessage`'s new params are optional and trailing; existing call sites compile unchanged.)

Contract notes for downstream roles:
- `TuningUpdate` (ambient interface, no implicit index signature) cannot be reached from `Record<string, unknown>` via a single `as` cast — the SSE case uses `parsed as unknown as TuningUpdate` (tsc-required double assertion); keep this form.
- Route path uses a literal first segment `/tuning-profile/{world_id}` to avoid colliding with `/{chat_id}`. `world_id` is `str` in the path, cast `int(...)` before the service call (project convention).
- `tuning_service` stub bodies raise `NotImplementedError`; the routes are wired and import-clean, so the GET/PUT endpoints return 500 at runtime until the coder implements `get_profile`/`update_profile`. The `_to_response` helper is already correct.

### Step 004 — frozen interface (2026-06-30)
- `backend/app/services/prompts/retune_prompt.py` — `build_retune_prompt(dimension: str, current_tuning: str, rejections: list[ChatGenerationFeedback], accepted_content: str) -> str` — new
- `backend/app/services/prompts/__init__.py` — re-export `build_retune_prompt` (import + `__all__`) — new
- `backend/app/services/retune_service.py` — `RetuneEmitter = Callable[[str, dict[str, str]], Awaitable[None]]` (type alias) — new
- `backend/app/services/retune_service.py` — `async def maybe_retune(session_id: int, user_id: int, world_id: int, turn_number: int, accepted_content: str, model_id: str | None, emitter: RetuneEmitter | None = None) -> None` — new
- `backend/app/services/chat_service.py` — `continue_chat` accept hook: writes one `verdict="approved"` `ChatGenerationFeedback` row + calls `retune_service.maybe_retune(..., emitter=None)` at function end — changed (signature `async def continue_chat(session_id: int, user_id: int, variant_index: int) -> None` unchanged; body wiring added)
- Caller-compile edits (out of Source-files scope): None.

Contract notes for downstream roles:
- `model_id` is typed `str | None` to match `ChatSession.text_model_id` (nullable); the hook passes `chat.text_model_id`. The coder decides null handling.
- `emitter` is `(event_name, payload) -> Awaitable[None]`; the caller owns editor-role gating and transport. `maybe_retune` invokes it (when non-None) with the post-retune `tuning_update` payload `{"plan_tuning", "tone_tuning", "world_id"}` (all str). The non-streaming accept hook passes `None`.
- `maybe_retune` stub raises `NotImplementedError`; it is wired unconditionally into `continue_chat`, so the accept path (explicit + implicit) raises at runtime until the coder implements the service. The `approved`-feedback write executes before the `maybe_retune` call, so DoD-5's assertion still sees the exception (true-red) until implementation lands.

## Notes & Issues

- Step 006: `rejectComment`/`rejectCommentOpen` are single shared observables (frozen design), so toggling the comment input opens it on every visible assistant `MessageBubble` at once. Acceptable for the typical single-active-reject flow; flag if per-message scoping is later required.
- Step 004: `maybe_retune` treats `model_id is None` (session has no `text_model_id`) as a no-op — no LLM call, no profile change, no emission — since no model means no revised text can be produced. Logged at INFO.
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

### Step 004 — tests (2026-06-30)
- `backend/tests/test_retune_service.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5, DoD-6.
  - DoD-1: clean accept (zero `rejected` rows; an `approved` row present) → `maybe_retune` makes no LLM `chat` call (`fake.calls == []`), profile plan/tone unchanged, no `tuning_update` emitted.
  - DoD-2: parametrized — only `plan`-scope reject updates `plan_tuning` (tone unchanged); only `text`-scope reject updates `tone_tuning` (plan unchanged); exactly one dimension sent to LLM (1 `chat` call).
  - DoD-3: null-scope reject retunes BOTH dimensions and sends both (2 `chat` calls).
  - DoD-4: no prior profile + plan-scope reject → profile created (fresh int id), `plan_tuning` persisted/re-fetchable for the same `(user, world)`, untargeted `tone_tuning` preserved as default "".
  - DoD-5: integration — regenerate (whole chain via step-003 harness) then `chat_service.continue_chat(..., variant_index=0)`; exactly one `verdict="approved"` row for the turn via `generation_feedback.list_by_turn` (filtered).
  - DoD-6: stub `RetuneEmitter` captures one `tuning_update` event whose payload carries post-retune `plan_tuning` (retuned), `tone_tuning` (unchanged), `world_id == str(world_id)`, all values str.
  - Harness: LLM mocked at consuming seams — `retune_service.get_llm_client_for_model` (non-tool `chat` → constant `"RETUNED"`, call count = targeted-dimension count; patched with `raising=False` so the seam can be set before the coder imports the symbol) and, for DoD-5, `chain_generation_service.get_llm_client_for_model`. Profiles/feedback seeded directly via `db/tuning_profiles` + `db/generation_feedback` (FK enforcement off in test DB). Red-gate: `maybe_retune` stub raises `NotImplementedError` (wired into `continue_chat`), so all tests fail for the right reason until implemented.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 [manual/live, no test]

### Step 005 — tests (2026-06-30)
- `backend/tests/test_tuning_profile_api.py` — covers DoD-1, DoD-2, DoD-3 — GET/PUT tuning-profile endpoints via the real FastAPI app with an authenticated player caller (`http_client` + `player_user`); rows seeded via `db/tuning_profiles`.
  - DoD-1: GET with no row → empty-string `plan_tuning`/`tone_tuning`, `world_id` as str, `id` is a str; GET with a seeded row → stored values + stored id as str.
  - DoD-2: PUT replaces `plan_tuning`/`tone_tuning` (id serializes as a str), persists in the db layer, and a subsequent GET returns the new values under the same id.
  - DoD-3: a second PUT for the same (user, world) keeps the same profile id (no duplicate / id churn); GET + db layer reflect the second PUT's values.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 [tsc-gated frontend, no backend test], DoD-5 [manual/live, no test]
