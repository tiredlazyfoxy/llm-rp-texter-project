# Feature 015 — background_retune — outcome (doc deltas for the architect)

Intended documentation changes after this feature ships. Supersedes parts of
feature 014 (`chat_preference_tuning`): the inline on-accept retune and the
editor-only `tuning_update` SSE event are replaced by a background, session-scoped,
polling-controlled retune.

## `docs/architecture/quick-reference.md`

- **SSE protocol / event table** — target: the SSE events section.
  Change: REMOVE the editor-only `tuning_update` event row. Reason: retune status is
  no longer pushed over SSE; it is polled via REST (D1). Note the removal explicitly
  so readers of feature 014's doc know it was superseded.

- **API endpoints table** — target: the chat/user API endpoints section.
  Change: ADD three session-scoped routes — `POST /{chat_id}/retune` (manual trigger,
  session-wide, ignores the auto turn-gate; cancel-and-restart),
  `POST /{chat_id}/retune/stop` (cancel without restart),
  `GET /{chat_id}/retune/status` (returns `RetuneStatusResponse`:
  `running`, `plan_tuning`, `tone_tuning`, `world_id`). Reason: new polling-based
  control surface for the background retune.

- **DB models** — target: the DB models section.
  Change: NONE. Reason: no new/changed persistent table — retune status lives only in
  an in-memory single-process registry; `ChatTuningProfile` / `ChatGenerationFeedback`
  are unchanged. State this explicitly so the architect does not expect a schema/JSONL
  delta.

## Backend / pipeline architecture doc

- **Retune mechanism** — target: the section describing feature 014's on-accept
  retune (chain pipeline / tuning).
  Change: REPLACE the "inline blocking retune on accept" description with the
  background model: an in-memory, per-session `retune_tasks` registry (single uvicorn
  process → safe process singleton; status resets to idle on restart), running the
  retune core as a detached `asyncio.Task` via `get_standalone_session` DAL access.
  Guarantees: ≤1 running per session; cancel-and-restart on a new trigger (D3); Stop
  cancels without restart. Triggers: auto on accept only when the accepted turn had
  ≥1 reject (D2 gate at the accept call site), plus a manual REST trigger that ignores
  the gate. Evidence: session-wide — all rejects across all turns
  (`generation_feedback.list_by_session`), not just the accepted turn. Reason:
  requirements 1, 2, 3, 4, 5, 6, 7.

- **Accept path** — target: the accept/`_record_accept_and_retune` description.
  Change: note the accept hook is now fire-and-forget (writes the `approved` row, then
  schedules a background job when the turn had a reject) and that the `emitter` /
  `pending_frames` / `tuning_update` plumbing was removed from
  `retune_service` / `chain_generation_service`. Reason: non-blocking accept (req 1)
  and SSE removal (D1).

- **New DAL** — target: the `db/generation_feedback` description if present.
  Change: add `list_by_session(session_id)` (all rows, all turns, created_at order).
  Reason: session-wide evidence gathering.

## Frontend architecture doc

- **Chat page retune UX** — target: the frontend chat/tuning section (feature 014's
  debug preferences panel).
  Change: describe the polling-based status loop on `ChatPageState`
  (`retuneRunning` / `retuneJustFinished`, start-on-open / stop-on-dispose), the
  settings-gear blink `Indicator` on finish, and the settings-panel running-state
  (disabled/grayed fields + spinner + Stop) with an idle-state "Retune now" button.
  Note REMOVAL of the `tuning_update` SSE handler (`onTuningUpdate`,
  `ChatSSEHandlers.onTuningUpdate`, the `TuningUpdate` type, and `applyTuningUpdate`).
  Reason: requirements 3, 4, 5, 6 and D1.

## Note

This feature supersedes the retune-delivery portions of feature 014. Where the
014 docs describe inline retune + `tuning_update` SSE, mark them as replaced by 015.

## Observations

_populated by the coder as steps complete_
