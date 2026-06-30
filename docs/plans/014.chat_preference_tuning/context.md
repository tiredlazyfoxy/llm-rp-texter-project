# Feature 014 — chat_preference_tuning

## Goal & scope

In-chat preference tuning: as the user chats, the app captures **approvals**
(accept / continue a generation) and **rejects** (regenerate, optionally with a
free-text comment). From that signal an LLM periodically **re-tunes** a
user-preference prompt injection so future generations get rejected less often.

A reject is **attributed** to one of two pipeline stages:

- **plan bad** → redo the whole generation chain (existing regenerate behavior).
- **text bad** → regenerate ONLY the writer stage, reusing the already-produced
  plan.

Two corresponding tuning injections accumulate per user:

- **plan-tuning** — injected into tool/planning stage prompts (`{PLAN_TUNING}`).
- **tone-tuning** — injected into the writer stage prompt (`{TONE_TUNING}`).

## Resolved design decisions (do not re-litigate)

1. **Tune scope = per (user, world).** A new persistent table keyed by
   `(user_id, world_id)` holds `plan_tuning` and `tone_tuning` text. It
   accumulates across all of the user's chats in that world.
2. **Retune trigger = on accept, only after the turn had ≥1 reject.** A clean
   turn (accepted first try) never triggers retune.
3. **Coverage = chain mode only for v1.** Simple mode and agentic mode are
   untouched. Tuning placeholders only need to work in
   `chain_generation_service.py`.
4. **Apply = auto-apply immediately; surface in a debug-gated preferences
   panel.** Retuned text takes effect on the next turn with no confirmation.
   The panel (show/edit `plan_tuning` + `tone_tuning`) is visible ONLY when the
   editor+/debug toggle is on. Players never see it.

## The two new persistent shapes (field-level contract; precise columns are
step 001's domain)

- **`ChatTuningProfile`** — per (user, world). Fields: snowflake `id`,
  `user_id`, `world_id`, `plan_tuning` (text, default ""), `tone_tuning`
  (text, default ""), `created_at`, `modified_at`. Uniqueness is logical on
  `(user_id, world_id)`; lookups/upserts go through that pair.
- **`ChatGenerationFeedback`** — per generation attempt, session-scoped.
  Fields: snowflake `id`, `session_id`, `turn_number`, `verdict`
  (`"approved"` | `"rejected"`), `scope` (`"plan"` | `"text"` | null — only
  set on rejects), `comment` (text | null), `content_snapshot` (the discarded
  or accepted assistant text), `plan_snapshot` (JSON string of the
  generation plan that produced it, or null), `created_at`.

These are referenced by steps 002–005; only step 001 defines the exact columns,
file template, db access, JSONL pairs, and cascade.

## Chain pipeline map (referenced by steps 002, 003, 004)

All in `backend/app/services/chain_generation_service.py`:

- `generate_chain_response(...)` — generation entry.
- `regenerate_chain_response(...)` — regenerate entry; today always re-runs the
  whole chain.
- `_run_chain_generation(...)` — the run loop. Loops `pipeline.stages`: tool
  stage → `_run_tool_stage` (phase "planning"); writer stage →
  `_run_writer_stage` (phase "writing"); then `_finalize_chain`.
- `_resolve_tool_prompt(...)` / `_resolve_writer_prompt(...)` — when
  `stage.prompt` is non-empty, call `_build_placeholder_values(...)` then
  `resolve_prompt_template(stage.prompt, **values)`; else fall back to legacy
  prompt builders.
- `_build_placeholder_values(...)` — maps placeholder names → runtime strings.
  This is the single injection point for new `PLAN_TUNING` / `TONE_TUNING`
  values.

The `{DECISION}` / `DecisionState` flow is the precedent for threading a
dynamic per-session value into stage prompts. Tuning is simpler: the profile is
loaded **once** at generation start (no mid-run mutation), so it is passed down
as plain strings — no mutable holder.

## Placeholder injection mechanism (referenced by steps 002, 004)

- `resolve_prompt_template(template, **values)` in
  `backend/app/services/prompts/prompt_injection.py` substitutes any
  `{UPPER_SNAKE}` token whose name matches a supplied kwarg; unknown tokens are
  left as-is. **No change needed to add new tokens** — register the name and
  supply the value.
- `PLACEHOLDER_REGISTRY` in
  `backend/app/services/prompts/placeholder_registry.py` lists known
  placeholders (surfaced to the admin pipeline-config UI). New names go here.
- Default templates in `backend/app/services/prompts/default_templates.py`
  (`DEFAULT_TOOL_PROMPT`, `DEFAULT_DIRECTOR_PROMPT`, `DEFAULT_WRITER_PROMPT`)
  embed the new tokens so the feature works out of the box on newly created
  pipelines. **Existing pipelines do not get the token automatically** — an
  admin must add it to their stage prompts; this is accepted for v1 (see Open
  questions in the hand-back).

## SSE protocol — new event (referenced by steps 004, 005)

A new **editor-only** SSE event `tuning_update` carries the post-retune
`plan_tuning` / `tone_tuning` so the debug preferences panel can refresh live.
It is filtered by `caller_role` exactly like the other editor-only events
(`phase`, `variants_update`, etc.). Players never receive it.

## Preferences API (referenced by steps 004, 005)

Read/write endpoints for the current user's `(user_id, world_id)` tuning
profile: a GET returning the profile and a PUT replacing `plan_tuning` /
`tone_tuning` (manual edit + revert from the debug panel). Defined in step 005's
route work; the db/service access it reuses comes from step 001/004.

## Conventions to honor (project-wide)

- **Layers**: `routes/` (HTTP only) → `services/` (business logic, no DB
  sessions) → `db/` (session-free namespace modules; all `AsyncSession`
  internal). No `session`/`select` outside `db/`.
- **Models**: SQLModel for tables; Pydantic `BaseModel` for all API schemas;
  `TypedDict` for internal passing. No free dicts, no `any`.
- **Snowflake IDs** assigned in the service layer:
  `from app.services import snowflake as snowflake_svc; snowflake_svc.generate_id()`.
  Models declare `id: int = Field(primary_key=True)` with no default. IDs
  serialize as **strings** in API responses.
- **JSONL import/export** must be updated in the same change as any new/changed
  DB model (project rule).
- **Prompts** live one-file-per-prompt under
  `backend/app/services/prompts/` with the 5-section docstring (PURPOSE, USAGE,
  VARIABLES, DESIGN RATIONALE, CHANGELOG), re-exported via `__init__.py`.
- **Frontend**: TS + React + MobX, `observer` on every component, no `useState`
  for reactive state, page-state classes with free-function actions, all HTTP
  in `src/api/`, DTOs in `src/types/`, no runtime validation; backend Pydantic
  is the source of truth and `.d.ts` mirrors it exactly.

## Build / test commands

- Backend tests: `cd backend && .venv/Scripts/python -m pytest`
- Frontend typecheck: `cd frontend && npx tsc --noEmit`
- Frontend build (typecheck + bundle): `cd frontend && npm run build`
- No backend static type-check; no linter configured.

## Architecture pointers

- `docs/architecture/quick-reference.md` — condensed DB models, API endpoints,
  SSE protocol, tools, placeholders. Read first for cross-cutting context.

## Step map / files touched across steps

| Step | Theme | Primary surface |
|------|-------|-----------------|
| 001 | Data layer | new models `chat_tuning_profile.py`, `chat_generation_feedback.py`; `db/tuning_profiles.py`, `db/generation_feedback.py`; `db/engine.py`; `db/chats.py` (cascade); `services/db_import_export.py`; new Pydantic schemas |
| 002 | Tuning injection | `placeholder_registry.py`, `default_templates.py`, `chain_generation_service.py` (`_build_placeholder_values` + profile load) |
| 003 | Reject attribution + scoped regen | `models/schemas/chat.py` (RegenerateRequest), `routes/chat.py`, `chat_agent_service.py`, `chain_generation_service.py` (writer-only regen + rejected feedback write) |
| 004 | Retune service + trigger | new prompt file, new `services/retune_service.py`, `chat_service.py` (continue/accept hook), SSE `tuning_update` emit |
| 005 | Frontend | `api/chat.ts`, `types/chat.d.ts`, `chatPageState.ts`, `MessageBubble.tsx`/`ChatInput.tsx`, `ChatSettingsPanel.tsx`, new preferences api/types; backend GET/PUT route for profile |

Dependency order: 002←001, 003←001, 004←001+003, 005←001-004.
