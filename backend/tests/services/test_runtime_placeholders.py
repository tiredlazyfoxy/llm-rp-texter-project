"""Tests for the pure `apply_runtime_placeholders` helper."""

import json
import logging

from app.models.world import StatScope, StatType, WorldStatDefinition
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


# --- Feature 012: namespaced stat tokens ---------------------------------


def _stat_def(
    *,
    name: str,
    scope: StatScope,
    stat_type: StatType,
    enum_values: list[str] | None = None,
    hidden: bool = False,
) -> WorldStatDefinition:
    return WorldStatDefinition(
        id=1,
        world_id=1,
        name=name,
        description="",
        scope=scope,
        stat_type=stat_type,
        default_value="0",
        min_value=None,
        max_value=None,
        enum_values=json.dumps(enum_values) if enum_values is not None else None,
        hidden=hidden,
    )


def _stat_ctx(
    *,
    stat_definitions: list[WorldStatDefinition],
    stat_values: dict[tuple[str, str], int | str | list[str]],
) -> RuntimePlaceholderContext:
    return {
        "character_name": "Aelric",
        "location_name": "The Stone Hall",
        "location_summary": "Quiet stone hall.",
        "stat_definitions": stat_definitions,
        "stat_values": stat_values,
    }


def test_int_stat_renders_as_string() -> None:
    defs = [_stat_def(name="HEALTH", scope=StatScope.character, stat_type=StatType.int_)]
    ctx = _stat_ctx(stat_definitions=defs, stat_values={("user", "HEALTH"): 42})

    result = apply_runtime_placeholders("HP: {USER:HEALTH}", ctx)

    assert result == "HP: 42"


def test_enum_stat_renders_as_value() -> None:
    defs = [
        _stat_def(
            name="WEATHER",
            scope=StatScope.world,
            stat_type=StatType.enum_,
            enum_values=["sunny", "rainy", "stormy"],
        )
    ]
    ctx = _stat_ctx(stat_definitions=defs, stat_values={("world", "WEATHER"): "rainy"})

    result = apply_runtime_placeholders("It is {WORLD:WEATHER} today.", ctx)

    assert result == "It is rainy today."


def test_set_stat_renders_comma_space_joined_in_declared_order() -> None:
    defs = [
        _stat_def(
            name="TAGS",
            scope=StatScope.character,
            stat_type=StatType.set_,
            enum_values=["alpha", "beta", "gamma", "delta"],
        )
    ]
    # Stored in non-declared order; render must follow enum_values order.
    ctx = _stat_ctx(
        stat_definitions=defs,
        stat_values={("user", "TAGS"): ["gamma", "alpha"]},
    )

    result = apply_runtime_placeholders("Tags: {USER:TAGS}", ctx)

    assert result == "Tags: alpha, gamma"


def test_empty_set_renders_empty_string() -> None:
    defs = [
        _stat_def(
            name="TAGS",
            scope=StatScope.character,
            stat_type=StatType.set_,
            enum_values=["a", "b"],
        )
    ]
    ctx = _stat_ctx(stat_definitions=defs, stat_values={("user", "TAGS"): []})

    result = apply_runtime_placeholders("Tags: '{USER:TAGS}'", ctx)

    assert result == "Tags: ''"


def test_hidden_stat_still_substitutes() -> None:
    defs = [
        _stat_def(
            name="SECRET",
            scope=StatScope.character,
            stat_type=StatType.int_,
            hidden=True,
        )
    ]
    ctx = _stat_ctx(stat_definitions=defs, stat_values={("user", "SECRET"): 7})

    result = apply_runtime_placeholders("[{USER:SECRET}]", ctx)

    assert result == "[7]"


def test_unknown_name_renders_empty_and_logs_debug(
    caplog: "logging.LogCaptureFixture",
) -> None:
    defs = [_stat_def(name="HEALTH", scope=StatScope.character, stat_type=StatType.int_)]
    ctx = _stat_ctx(stat_definitions=defs, stat_values={("user", "HEALTH"): 1})

    with caplog.at_level(logging.DEBUG, logger="app.services.runtime_placeholders"):
        result = apply_runtime_placeholders("[{USER:NOPE}]", ctx)

    assert result == "[]"
    assert any(
        "{USER:NOPE}" in rec.message and rec.levelno == logging.DEBUG
        for rec in caplog.records
    )


def test_unknown_owner_namespace_left_untouched() -> None:
    defs = [_stat_def(name="FOO", scope=StatScope.character, stat_type=StatType.int_)]
    ctx = _stat_ctx(stat_definitions=defs, stat_values={("user", "FOO"): 1})

    result = apply_runtime_placeholders("Look: {NPC:FOO}", ctx)

    # NPC namespace is not USER/WORLD, so the regex does not match
    # and the literal token survives untouched.
    assert result == "Look: {NPC:FOO}"


def test_lowercase_stat_token_left_untouched() -> None:
    defs = [_stat_def(name="HEALTH", scope=StatScope.character, stat_type=StatType.int_)]
    ctx = _stat_ctx(stat_definitions=defs, stat_values={("user", "HEALTH"): 9})

    result = apply_runtime_placeholders("HP: {USER:Health}", ctx)

    # Mixed-case name fails the uppercase-only regex; literal survives.
    assert result == "HP: {USER:Health}"


def test_missing_stat_snapshots_yield_empty_with_debug_log(
    caplog: "logging.LogCaptureFixture",
) -> None:
    # No stat_definitions / stat_values keys at all.
    ctx: RuntimePlaceholderContext = {
        "character_name": "Aelric",
        "location_name": "Hall",
        "location_summary": "Quiet.",
    }

    with caplog.at_level(logging.DEBUG, logger="app.services.runtime_placeholders"):
        result = apply_runtime_placeholders(
            "HP {USER:HEALTH} weather {WORLD:WEATHER}", ctx
        )

    assert result == "HP  weather "
    debug_messages = [rec.message for rec in caplog.records if rec.levelno == logging.DEBUG]
    assert any("{USER:HEALTH}" in msg for msg in debug_messages)
    assert any("{WORLD:WEATHER}" in msg for msg in debug_messages)


def test_explicit_none_stat_snapshots_yield_empty_without_raising() -> None:
    ctx: RuntimePlaceholderContext = {
        "character_name": "Aelric",
        "location_name": "Hall",
        "location_summary": "Quiet.",
        "stat_definitions": None,
        "stat_values": None,
    }

    # Must not raise; missing snapshots resolve to empty string.
    result = apply_runtime_placeholders("[{USER:ANY}]", ctx)

    assert result == "[]"


def test_namespaced_and_feature_010_tokens_coexist() -> None:
    # Regression: the namespaced regex pass and the legacy literal-string
    # pass must not interfere with each other in the same string.
    defs = [_stat_def(name="HEALTH", scope=StatScope.character, stat_type=StatType.int_)]
    ctx = _stat_ctx(stat_definitions=defs, stat_values={("user", "HEALTH"): 12})

    text = "Hi {CHARACTER_NAME}, HP={USER:HEALTH} at {LOCATION_NAME}."
    result = apply_runtime_placeholders(text, ctx)

    assert result == "Hi Aelric, HP=12 at The Stone Hall."


def test_world_owner_routes_to_world_scope_definition() -> None:
    # A stat named HEALTH in the character scope must NOT match
    # {WORLD:HEALTH}; the resolver pairs owner with scope.
    defs = [
        _stat_def(name="HEALTH", scope=StatScope.character, stat_type=StatType.int_),
    ]
    ctx = _stat_ctx(
        stat_definitions=defs,
        stat_values={("user", "HEALTH"): 5, ("world", "HEALTH"): 99},
    )

    result = apply_runtime_placeholders("[{WORLD:HEALTH}]", ctx)

    # No world-scope definition exists, so render is empty.
    assert result == "[]"
