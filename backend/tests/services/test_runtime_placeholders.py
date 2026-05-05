"""Tests for the pure `apply_runtime_placeholders` helper."""

from app.services.runtime_placeholders import (
    RuntimePlaceholderContext,
    apply_runtime_placeholders,
)


def _ctx() -> RuntimePlaceholderContext:
    return {
        "character_name": "Aelric",
        "location_name": "The Stone Hall",
        "location_summary": "A quiet stone hall lit by torches.",
    }


def test_substitutes_all_three_tokens() -> None:
    text = (
        "Welcome, {CHARACTER_NAME}. You are at {LOCATION_NAME}. "
        "{LOCATION_SUMMARY}"
    )
    result = apply_runtime_placeholders(text, _ctx())

    assert "Aelric" in result
    assert "The Stone Hall" in result
    assert "A quiet stone hall lit by torches." in result
    assert "{CHARACTER_NAME}" not in result
    assert "{LOCATION_NAME}" not in result
    assert "{LOCATION_SUMMARY}" not in result


def test_none_context_returns_text_unchanged() -> None:
    text = "Hello {CHARACTER_NAME} at {LOCATION_NAME} -- {LOCATION_SUMMARY}"
    assert apply_runtime_placeholders(text, None) == text


def test_idempotent_on_already_substituted_text() -> None:
    text = (
        "Welcome, {CHARACTER_NAME}. You are at {LOCATION_NAME}. "
        "{LOCATION_SUMMARY}"
    )
    once = apply_runtime_placeholders(text, _ctx())
    twice = apply_runtime_placeholders(once, _ctx())
    assert once == twice


def test_lowercase_variants_are_not_substituted() -> None:
    text = "Hello {character_name} at {location_name} -- {location_summary}"
    result = apply_runtime_placeholders(text, _ctx())

    # Lowercase tokens must survive untouched (uppercase-only contract).
    assert "{character_name}" in result
    assert "{location_name}" in result
    assert "{location_summary}" in result
    # And the values must NOT have been substituted in.
    assert "Aelric" not in result
    assert "The Stone Hall" not in result


def test_text_without_tokens_returned_unchanged() -> None:
    text = "Just some plain prose with no placeholders at all."
    assert apply_runtime_placeholders(text, _ctx()) == text


def test_empty_string_returned_unchanged() -> None:
    assert apply_runtime_placeholders("", _ctx()) == ""
    assert apply_runtime_placeholders("", None) == ""
