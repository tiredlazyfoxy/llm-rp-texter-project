# Fast feature 003 — reject_comment_steer

| Status | Verifier | Date |
|--------|----------|------|
| done   | PASS     | 2026-07-02 |

## Files Changed

- `backend/app/services/chain_generation_service.py` — filled `_merge_reject_comment` stub body (pure reject-comment → user_instructions merge helper)

## Skeleton

### Frozen interface (2026-07-02)
- `backend/app/services/chain_generation_service.py` — `_merge_reject_comment(user_instructions: str | None, comment: str | None) -> str | None` — new module-level pure helper; stub body `raise NotImplementedError`. Frozen contract the test-coder binds to.
- `backend/app/services/chain_generation_service.py` — `regenerate_chain_response` call-site wiring: added `user_instructions = _merge_reject_comment(user_instructions, comment)` after the `user_instructions` load (~line 936), before the `_run_chain_generation` call (~978). No signature change; no new parameter to `_run_chain_generation`, `_run_tool_stage`, `_run_writer_stage`, or `_build_placeholder_values`.
- Caller-compile edits (out of Source-files scope): None.

## Tests

### Tests (2026-07-02)
- `backend/tests/test_reject_comment_steer.py` — unit tests for `_merge_reject_comment`, bound to the frozen skeleton signature.
  - `test_merge_with_existing_instructions_contains_all` — covers DoD-1 — merged result contains original instructions + comment + is transformed (framing marker, tolerant).
  - `test_merge_with_no_instructions_no_separator_artifacts` — covers DoD-2 — None/empty instructions yield non-empty stripped result containing the comment, no separator artifacts.
  - `test_none_comment_returns_instructions_unchanged` — covers DoD-3 — None comment returns instructions unchanged (incl. None → None).
  - `test_empty_or_whitespace_comment_returns_instructions_unchanged` — covers DoD-4 — `""` and `"   "` comment return instructions unchanged.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 [manual/live, no test], DoD-6 [manual/live, no test]

## Notes & Issues

_populated by the coder when worth saying_
