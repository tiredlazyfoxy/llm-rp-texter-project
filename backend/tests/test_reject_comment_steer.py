"""Unit tests for the reject-comment merge helper (fast feature 003).

Bound to the frozen skeleton signature:

- ``app.services.chain_generation_service._merge_reject_comment(
  user_instructions: str | None, comment: str | None) -> str | None`` —
  module-level pure helper, no I/O.

Expected values come from the plan's DoD only. The exact reject-feedback
framing sentence is the coder's choice within the plan's guidance, so the
framing is asserted tolerantly (result differs from / is longer than the
original, comment + original substrings present) rather than pinned verbatim.
"""

import pytest

from app.services.chain_generation_service import _merge_reject_comment


# DoD-1: non-empty comment + non-empty user_instructions -> result contains the
# original instructions, contains the comment, and carries reject-feedback
# framing (tolerant: differs from original and is longer than it).
def test_merge_with_existing_instructions_contains_all():
    user_instructions = "Focus on the tavern scene."
    comment = "Too rushed, slow it down."

    result = _merge_reject_comment(user_instructions, comment)

    assert result is not None
    assert user_instructions in result  # original instructions preserved
    assert comment in result  # reject comment threaded in
    # framing marker: result must be transformed, not identity
    assert result != user_instructions
    assert len(result) > len(user_instructions)


# DoD-2: non-empty comment + None/empty user_instructions -> non-empty result
# containing the comment, with no spurious leading/trailing separator artifacts.
@pytest.mark.parametrize("user_instructions", [None, ""])
def test_merge_with_no_instructions_no_separator_artifacts(user_instructions):
    comment = "Make the villain more sympathetic."

    result = _merge_reject_comment(user_instructions, comment)

    assert result is not None
    assert result != ""
    assert comment in result  # comment becomes the whole framed value
    assert result == result.strip()  # no leading/trailing whitespace artifacts


# DoD-3: None comment leaves user_instructions unchanged (identity), including
# when user_instructions is itself None.
@pytest.mark.parametrize(
    "user_instructions",
    ["some text", None],
)
def test_none_comment_returns_instructions_unchanged(user_instructions):
    result = _merge_reject_comment(user_instructions, None)

    assert result == user_instructions


# DoD-4: empty-string and whitespace-only comment each leave user_instructions
# unchanged (no framing appended).
@pytest.mark.parametrize("comment", ["", "   "])
def test_empty_or_whitespace_comment_returns_instructions_unchanged(comment):
    user_instructions = "Keep the pacing tense."

    result = _merge_reject_comment(user_instructions, comment)

    assert result == user_instructions
