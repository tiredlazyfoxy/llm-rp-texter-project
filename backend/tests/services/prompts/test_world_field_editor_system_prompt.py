"""Tests for `build_world_field_editor_system` placeholder awareness.

Covers the `initial_message` field gaining the multi-line "Runtime
Placeholders" block (with doubled-brace escaping in `_FIELD_ROLES` so the
surrounding `.format(world_name=...)` call leaves literal `{CHARACTER_NAME}`),
plus a regression assert that the `description` field role is **not**
modified — `description` does not get runtime substitution.
"""

from __future__ import annotations

from app.services.prompts.world_field_editor_system_prompt import (
    build_world_field_editor_system,
)


_RUNTIME_TOKENS = ("{CHARACTER_NAME}", "{LOCATION_NAME}", "{LOCATION_SUMMARY}")


def _build(field_type: str) -> str:
    return build_world_field_editor_system(
        field_type=field_type,
        world_name="Mythos",
        world_description="A grim fantasy realm.",
        world_lore="Ancient ruins dot the landscape.",
        current_content="",
    )


def test_initial_message_includes_runtime_placeholders_block() -> None:
    output = _build("initial_message")

    assert "Runtime Placeholders" in output
    for token in _RUNTIME_TOKENS:
        assert token in output, f"missing literal token {token}"


def test_initial_message_tokens_render_with_literal_single_braces() -> None:
    """Doubled-brace escaping must survive `.format(world_name=...)`.

    The rendered prompt must contain literal `{CHARACTER_NAME}` — not
    `CHARACTER_NAME` (over-escaped or unescaped) and not
    `{{CHARACTER_NAME}}` (under-escaped).
    """
    output = _build("initial_message")

    for token in _RUNTIME_TOKENS:
        # Single-brace literal survived format().
        assert token in output
        # No bare-name leak (would mean format() consumed the braces).
        bare = token.strip("{}")
        # `bare` could still appear inside the literal `{TOKEN}` — that's
        # fine; what we want is that `{{TOKEN}}` did not survive (the
        # double-brace escape sequence should have collapsed to single).
        assert f"{{{token}}}" not in output, (
            f"double-braced {token} leaked into output — escaping failed"
        )
        # Also no bare-name without any braces.
        # We test by removing literal `{TOKEN}` occurrences and checking
        # that no stray `TOKEN` remains.
        stripped = output.replace(token, "")
        assert bare not in stripped, (
            f"unbraced {bare} appears in output — format() consumed the braces"
        )


def test_initial_message_explanation_mentions_chat_time_substitution() -> None:
    output = _build("initial_message")
    assert "chat time" in output


def test_description_does_not_include_runtime_placeholders_block() -> None:
    output = _build("description")

    assert "Runtime Placeholders" not in output
    for token in _RUNTIME_TOKENS:
        assert token not in output


def test_system_prompt_does_not_include_runtime_placeholders_block() -> None:
    """Sanity: only `initial_message` carries the substitution-aware block."""
    output = _build("system_prompt")
    assert "Runtime Placeholders" not in output
