# Feature 014 — chat_preference_tuning — outcome

Intended documentation changes after this feature ships. The architect applies
these to `docs/architecture/` during finalization. Grouped by target doc.

## docs/architecture/quick-reference.md

- **DB models** — Add `ChatTuningProfile` (per user+world: plan_tuning,
  tone_tuning, timestamps) and `ChatGenerationFeedback` (session-scoped:
  turn_number, verdict approved/rejected, scope plan/text/null, comment,
  content_snapshot, plan_snapshot, created_at) to the condensed model list.
  Reason: two new persistent tables added in step 001.
- **Placeholders** — Add `PLAN_TUNING` (tool/planning stages) and `TONE_TUNING`
  (writer stage) to the placeholder list. Reason: registered in step 002 and
  injected via `_build_placeholder_values`.
- **Default templates** — Note that `DEFAULT_TOOL_PROMPT` /
  `DEFAULT_DIRECTOR_PROMPT` now embed `{PLAN_TUNING}` and `DEFAULT_WRITER_PROMPT`
  embeds `{TONE_TUNING}`; existing pipelines must add the tokens manually.
  Reason: step 002 default-template change + the no-migration decision.
- **SSE protocol** — Add the editor-only `tuning_update` event (payload:
  plan_tuning, tone_tuning, world id). Reason: emitted by the retune service in
  step 004, consumed by the frontend in steps 005/006.
- **API endpoints** — Add the regenerate `scope`/`comment` fields and the new
  tuning-profile GET/PUT endpoints. Reason: steps 003 and 005.

## docs/architecture (DB models / import-export doc, whichever holds the registry)

- Document that `ChatTuningProfile` and `ChatGenerationFeedback` participate in
  JSONL import/export (`TABLE_REGISTRY` tuples) and that `delete_session`
  cascades `ChatGenerationFeedback`. Reason: step 001 import/export + cascade.

## docs/architecture (backend / pipeline doc)

- Describe the two-dimension tuning loop: reject attribution (plan vs text),
  writer-only regenerate reusing the stored plan, and the on-accept retune
  trigger (fires only when the turn had ≥1 reject), scoped per (user, world).
  Reason: steps 003 + 004 introduce the behavior.
- Note the new retune prompt file under `services/prompts/` and the
  `retune_service` / `tuning_service` modules. Reason: steps 004 + 005.

## docs/architecture (frontend doc)

- Document the chain-mode reject-with-scope/comment affordance and the
  debug-gated tuning preferences panel (editor+ only), plus the new
  `api/tuningProfile.ts` client and `types/tuningProfile.d.ts`. Reason: steps
  005 + 006.

## CLAUDE memory / stage tracker

- Mark feature 014 (chat_preference_tuning) delivered; note chain-mode-only
  scope for v1 (simple/agentic untouched). Reason: scope decision 3.
