"""Tests for `build_document_editor_system` placeholder awareness.

The document editor must teach the LLM the runtime-placeholder vocabulary
established by feature 010 — the trio `{CHARACTER_NAME}`, `{LOCATION_NAME}`,
`{LOCATION_SUMMARY}`. The "## Runtime Placeholders" section is included
unconditionally for every doc_type.

Feature 012 step 003 adds a "## Stat Placeholders" section listing the
world's ``WorldStatDefinition`` names as literal ``{USER:NAME}`` /
``{WORLD:NAME}`` tokens.
"""

from __future__ import annotations

import pytest

from app.models.world import StatScope, StatType, WorldStatDefinition
from app.services.prompts.document_editor_system_prompt import (
    build_document_editor_system,
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


def _build(doc_type: str, *, stat_defs: list[WorldStatDefinition] | None = None) -> str:
    return build_document_editor_system(
        doc_type=doc_type,
        world_name="Mythos",
        world_description="A grim fantasy realm.",
        world_lore="Ancient ruins dot the landscape.",
        current_content="",
        stat_defs=stat_defs,
    )


@pytest.mark.parametrize("doc_type", ["location", "npc", "lore_fact"])
def test_includes_runtime_placeholders_section_for_every_doc_type(doc_type: str) -> None:
    output = _build(doc_type)

    assert "Runtime Placeholders" in output
    for token in _RUNTIME_TOKENS:
        assert token in output, f"missing literal token {token} for doc_type={doc_type}"


@pytest.mark.parametrize("doc_type", ["location", "npc", "lore_fact"])
def test_explanation_mentions_chat_time_substitution(doc_type: str) -> None:
    output = _build(doc_type)
    # The explanation must convey that substitution happens at chat time.
    assert "chat time" in output


def test_section_present_even_with_empty_world_context() -> None:
    output = build_document_editor_system(
        doc_type="location",
        world_name="Mythos",
        world_description="",
        world_lore="",
        current_content="",
    )
    assert "## Runtime Placeholders" in output
    for token in _RUNTIME_TOKENS:
        assert token in output


def test_section_present_with_tools_enabled() -> None:
    output = build_document_editor_system(
        doc_type="npc",
        world_name="Mythos",
        world_description="",
        world_lore="",
        current_content="",
        enable_tools=True,
    )
    assert "## Runtime Placeholders" in output
    for token in _RUNTIME_TOKENS:
        assert token in output


# --- Stat Placeholders section (feature 012 step 003) ---


@pytest.mark.parametrize("doc_type", ["location", "npc", "lore_fact"])
def test_stat_section_emits_literal_user_and_world_tokens(doc_type: str) -> None:
    output = _build(doc_type, stat_defs=_STAT_DEFS)

    assert "## Stat Placeholders" in output
    # Every stat name appears as a literal namespaced token.
    assert "{USER:HEALTH}" in output
    assert "{USER:INVENTORY}" in output
    assert "{USER:MOOD}" in output
    assert "{WORLD:WEATHER}" in output
    assert "{WORLD:DOOMSDAY}" in output


def test_stat_section_uses_owner_namespace_per_scope() -> None:
    output = _build("location", stat_defs=_STAT_DEFS)
    # Character-scope stats render with the USER prefix, never WORLD.
    assert "{WORLD:HEALTH}" not in output
    assert "{USER:WEATHER}" not in output


def test_stat_section_lists_hidden_stats() -> None:
    """Hidden stats still substitute at chat runtime, so they must appear."""
    output = _build("npc", stat_defs=_STAT_DEFS)
    assert "{USER:MOOD}" in output
    assert "{WORLD:DOOMSDAY}" in output


def test_stat_section_instructs_to_preserve_verbatim() -> None:
    output = _build("location", stat_defs=_STAT_DEFS)
    # Imperative phrasing telling the LLM to keep placeholders literal.
    assert "verbatim" in output


def test_stat_section_omitted_when_no_stat_defs() -> None:
    """Zero-stats branch: section is omitted entirely (no 'no stats defined' line)."""
    output = _build("location", stat_defs=[])
    assert "## Stat Placeholders" not in output
    # And nothing claims stats exist.
    assert "{USER:" not in output
    assert "{WORLD:" not in output


def test_stat_section_omitted_when_stat_defs_is_none() -> None:
    """Default ``None`` behaves the same as empty list."""
    output = _build("location", stat_defs=None)
    assert "## Stat Placeholders" not in output


def test_stat_section_present_with_tools_enabled() -> None:
    output = build_document_editor_system(
        doc_type="npc",
        world_name="Mythos",
        world_description="",
        world_lore="",
        current_content="",
        enable_tools=True,
        stat_defs=_STAT_DEFS,
    )
    assert "## Stat Placeholders" in output
    assert "{USER:HEALTH}" in output
    assert "{WORLD:WEATHER}" in output
