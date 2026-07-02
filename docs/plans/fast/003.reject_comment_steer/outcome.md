# Fast feature 003 — reject_comment_steer — outcome

Intended documentation changes after this fix ships. The architect applies these
to `docs/architecture/` during finalization. This refines feature 014's
regenerate behavior — fold it into 014's existing pipeline description rather
than adding a standalone entry where possible.

## docs/architecture (backend / pipeline doc — the feature-014 tuning-loop section)

- Refine the chain-mode reject description: a reject **comment** now steers the
  **immediate** whole-chain redo, not only the next-accept retune. The comment
  is merged (framed as reject feedback) into the existing `user_instructions`
  string inside `regenerate_chain_response`, so it reaches both the planning
  (tool) and writer stages via the existing `{USER_INSTRUCTIONS}` placeholder.
  Reason: this fix threads the previously-dropped comment into the re-run.
- Note that no new placeholder/token/parameter was introduced — the fix reuses
  the `{USER_INSTRUCTIONS}` channel and merges upstream of
  `_run_chain_generation`. Reason: explicit design decision to avoid a new
  injection path.
- Clarify scope: simple mode still discards reject scope/comment; this steering
  is chain-mode only. Reason: unchanged simple-mode behavior.

## CLAUDE memory / stage tracker

- Note feature 014 follow-up shipped (fast/003): chain-mode reject comments now
  steer the immediate regenerate. Reason: retrospective accuracy.

## Observations

_populated by the coder when implementation lands_
