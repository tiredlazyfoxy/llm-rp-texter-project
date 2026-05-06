"""Tests for `build_world_field_editor_system` placeholder awareness.

Covers the `initial_message` field gaining the multi-line "Runtime
Placeholders" block (with doubled-brace escaping in `_FIELD_ROLES` so the
surrounding `.format(world_name=...)` call leaves literal `{CHARACTER_NAME}`),
plus a regression assert that the `description` field role is **not**
modified — `description` does not get runtime substitution.

Feature 012 step 003 adds a "## Stat Placeholders" section listing the
world's ``WorldStatDefinition`` names as literal ``{USER:NAME}`` /
``{WORLD:NAME}`` tokens (every field type, gated only on whether any
stat defs were passed in).
"""

from __future__ import annotations

import pytest

from app.models.world import StatScope, StatType, WorldStatDefinition
from app.services.prompts.world_field_editor_system_prompt import (
    build_world_field_editor_system,
)


_RUNTIME_TOKENS = ("{CHARACTER_NAME}", "{LOCATION_NAME}", "{LOCATION_SUMMARY}")


def _stat(
    name: str,
    *,
    scope: StatScope = StatScope.character,
    stat_type: StatType = StatType.int_,
    hidden: bool = False,
) -> WorldStatDefinition:
    return WorldStatDefinition(
        id=0,
        world_id=0,
        name=name,
        description="",
        scope=scope,
        stat_type=stat_type,
        default_value="0",
        hidden=hidden,
    )


_STAT_DEFS: list[WorldStatDefinition] = [
    _stat("HEALTH", scope=StatScope.character, stat_type=StatType.int_),
    _stat("INVENTORY", scope=StatScope.character, stat_type=StatType.set_),
    _stat("MOOD", scope=StatScope.character, stat_type=StatType.enum_, hidden=True),
    _stat("WEATHER", scope=StatScope.world, stat_type=StatType.enum_),
    _stat("DOOMSDAY", scope=StatScope.world, stat_type=StatType.int_, hidden=True),
]


def _build(
    field_type: str,
    *,
    stat_defs: list[WorldStatDefinition] | None = None,
) -> str:
    return build_world_field_editor_system(
        field_type=field_type,
        world_name="Mythos",
        world_description="A grim fantasy realm.",
        world_lore="Ancient ruins dot the landscape.",
        current_content="",
        stat_defs=stat_defs,
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


# --- Stat Placeholders section (feature 012 step 003) ---


@pytest.mark.parametrize(
    "field_type", ["description", "system_prompt", "initial_message"]
)
def test_stat_section_emits_literal_user_and_world_tokens(field_type: str) -> None:
    output = _build(field_type, stat_defs=_STAT_DEFS)

    assert "## Stat Placeholders" in output
    assert "{USER:HEALTH}" in output
    assert "{USER:INVENTORY}" in output
    assert "{USER:MOOD}" in output
    assert "{WORLD:WEATHER}" in output
    assert "{WORLD:DOOMSDAY}" in output


def test_stat_section_uses_owner_namespace_per_scope() -> None:
    output = _build("description", stat_defs=_STAT_DEFS)
    assert "{WORLD:HEALTH}" not in output
    assert "{USER:WEATHER}" not in output


def test_stat_section_lists_hidden_stats() -> None:
    """Hidden stats still substitute at chat runtime, so they must appear."""
    output = _build("system_prompt", stat_defs=_STAT_DEFS)
    assert "{USER:MOOD}" in output
    assert "{WORLD:DOOMSDAY}" in output


def test_stat_section_instructs_to_preserve_verbatim() -> None:
    output = _build("description", stat_defs=_STAT_DEFS)
    assert "verbatim" in output


@pytest.mark.parametrize(
    "field_type", ["description", "system_prompt", "initial_message"]
)
def test_stat_section_omitted_when_no_stat_defs(field_type: str) -> None:
    """Zero-stats branch: section is omitted entirely."""
    output = _build(field_type, stat_defs=[])
    assert "## Stat Placeholders" not in output
    assert "{USER:" not in output
    assert "{WORLD:" not in output


def test_stat_section_omitted_when_stat_defs_is_none() -> None:
    """Default ``None`` behaves the same as empty list."""
    output = _build("description", stat_defs=None)
    assert "## Stat Placeholders" not in output


def test_stat_tokens_are_not_clobbered_by_format_in_initial_message() -> None:
    """The `initial_message` role uses `.format(world_name=...)`; the stat
    section is appended *after* that format call so namespaced literals
    must survive untouched (no escaping concerns there, but regression-
    assert anyway).
    """
    output = _build("initial_message", stat_defs=_STAT_DEFS)
    # Single-brace literal — would be the symptom of a stray format() call.
    assert "{USER:HEALTH}" in output
    assert "{{USER:HEALTH}}" not in output
    assert "{WORLD:WEATHER}" in output
    assert "{{WORLD:WEATHER}}" not in output
