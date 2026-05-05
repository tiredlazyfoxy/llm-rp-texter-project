"""Tests for `build_document_editor_system` placeholder awareness.

The document editor must teach the LLM the runtime-placeholder vocabulary
established by feature 010 — the trio `{CHARACTER_NAME}`, `{LOCATION_NAME}`,
`{LOCATION_SUMMARY}`. The "## Runtime Placeholders" section is included
unconditionally for every doc_type.
"""

from __future__ import annotations

import pytest

from app.services.prompts.document_editor_system_prompt import (
    build_document_editor_system,
)


_RUNTIME_TOKENS = ("{CHARACTER_NAME}", "{LOCATION_NAME}", "{LOCATION_SUMMARY}")


def _build(doc_type: str) -> str:
    return build_document_editor_system(
        doc_type=doc_type,
        world_name="Mythos",
        world_description="A grim fantasy realm.",
        world_lore="Ancient ruins dot the landscape.",
        current_content="",
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
