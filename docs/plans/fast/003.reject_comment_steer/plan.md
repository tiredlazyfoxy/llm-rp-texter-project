# Fast feature 003 — reject_comment_steer — plan

## Goal

Thread a chain-mode reject **comment** into the immediate whole-chain
re-generation by merging it (framed as reject feedback) into the existing
`user_instructions` string, so the comment steers both the planning and writer
stages of the redo instead of only tuning future turns.

## Source files

- `backend/app/services/chain_generation_service.py` — add a pure merge helper and call it inside `regenerate_chain_response` before the `_run_chain_generation` call.

## Test files

- `backend/tests/test_reject_comment_steer.py` — new; unit tests for the merge helper.

(Source and test lists are disjoint.)

## Interface intent

- **`_merge_reject_comment` (new, module-level pure helper in `chain_generation_service.py`)**
  - Responsibility: given the current per-turn `user_instructions` (which may be
    `None`) and a reject `comment` (which may be `None`/empty/whitespace),
    return the `user_instructions` string to use for the re-run.
  - Behavior:
    - If `comment` is `None` or contains only whitespace, return
      `user_instructions` unchanged (identity — including returning `None` when
      it was `None`).
    - Otherwise, produce a feedback-framed line from the trimmed comment (e.g.
      wording along the lines of "The player rejected the previous attempt with
      this feedback: <comment>"). If `user_instructions` is non-empty, append
      the framed line to it (separated so both remain legible); if
      `user_instructions` is `None`/empty, the framed line becomes the whole
      returned value.
  - Inputs: current user-instructions text (optional) and the reject comment
    (optional). Output: the merged user-instructions text (optional).
  - Pure: no I/O, no session, no side effects — unit-testable in isolation.

- **`regenerate_chain_response` (modify existing)**
  - After `user_instructions` is loaded from the stored user message (~line 936)
    and before the `_run_chain_generation` call (~978–985), reassign
    `user_instructions = _merge_reject_comment(user_instructions, comment)`.
  - No signature change. No new parameter to `_run_chain_generation`. The
    existing `user_instructions=user_instructions` argument now carries the
    merged value, which reaches both stages via `_build_placeholder_values` →
    `{USER_INSTRUCTIONS}`. The feedback-write behavior at ~905–919 is unchanged.

## Definition of done

- **DoD-1** `[test]` A non-empty comment merged with existing non-empty
  `user_instructions` yields a result that contains the original instructions,
  contains the comment text, and contains the reject-feedback framing.
- **DoD-2** `[test]` A non-empty comment merged with `None` (or empty)
  `user_instructions` yields a non-empty result containing the comment text and
  the framing, with no spurious leading/trailing separator artifacts.
- **DoD-3** `[test]` A `None` comment leaves `user_instructions` unchanged
  (identity), including the case where `user_instructions` is itself `None`.
- **DoD-4** `[test]` An empty-string comment and a whitespace-only comment each
  leave `user_instructions` unchanged (no framing appended).
- **DoD-5** `[manual/live]` In `regenerate_chain_response`, the merged value is
  assigned to `user_instructions` before the `_run_chain_generation` call, so
  the same merged string is passed through to both the tool and writer stages
  (verified by code inspection — the argument at the call site is the merged
  variable, no new parameter added).
- **DoD-6** `[manual/live]` Existing feature-014 backend tests still pass
  (`test_reject_attribution.py` and siblings) — the feedback-write path and
  retune-on-accept behavior are unchanged.

## Out of scope

- Simple mode (`chat_agent_service.regenerate_response`) — still ignores
  scope/comment by design.
- Any new placeholder, registry entry, or template token.
- Any signature change to `_run_chain_generation`, `_run_tool_stage`,
  `_run_writer_stage`, or `_build_placeholder_values`.
- Changes to `retune_service` / the on-accept tuning trigger.
- Persistence/schema changes (the `ChatGenerationFeedback` write is untouched).
