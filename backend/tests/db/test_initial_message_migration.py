"""Tests for the one-time `initial_message` placeholder normalization
migration in `app.db.worlds`."""

from datetime import datetime, timezone

from app.db import worlds as worlds_db
from app.models.world import World, WorldStatus
from app.services.snowflake import generate_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _make_world(initial_message: str) -> int:
    world = World(
        id=generate_id(),
        name=f"migration-test-{generate_id()}",
        description="",
        lore="",
        character_template="",
        initial_message=initial_message,
        status=WorldStatus.draft,
        owner_id=None,
        created_at=_now(),
        modified_at=_now(),
    )
    await worlds_db.create(world)
    return world.id


async def test_normalize_rewrites_lowercase_and_is_idempotent() -> None:
    lower_id = await _make_world(
        "Hello {character_name}, welcome to {location_name}. {location_summary}"
    )
    upper_id = await _make_world(
        "Greetings {CHARACTER_NAME}, you are at {LOCATION_NAME}. {LOCATION_SUMMARY}"
    )
    mixed_id = await _make_world(
        "Hi {character_name}, you stand in {LOCATION_NAME}. {location_summary}"
    )

    # First pass: lowercase and mixed rows rewritten.
    changed = await worlds_db.normalize_initial_message_placeholders()
    assert changed == 2

    lower_world = await worlds_db.get_by_id(lower_id)
    upper_world = await worlds_db.get_by_id(upper_id)
    mixed_world = await worlds_db.get_by_id(mixed_id)

    assert lower_world is not None
    assert upper_world is not None
    assert mixed_world is not None

    for w in (lower_world, upper_world, mixed_world):
        assert "{character_name}" not in w.initial_message
        assert "{location_name}" not in w.initial_message
        assert "{location_summary}" not in w.initial_message
        assert "{CHARACTER_NAME}" in w.initial_message
        assert "{LOCATION_NAME}" in w.initial_message
        assert "{LOCATION_SUMMARY}" in w.initial_message

    # Second pass: idempotent — nothing left to change.
    changed_again = await worlds_db.normalize_initial_message_placeholders()
    assert changed_again == 0


async def test_rewrite_initial_message_tokens_pure_helper() -> None:
    src = "{character_name} at {location_name}: {location_summary}"
    out = worlds_db.rewrite_initial_message_tokens(src)
    assert out == "{CHARACTER_NAME} at {LOCATION_NAME}: {LOCATION_SUMMARY}"

    # Idempotent.
    assert worlds_db.rewrite_initial_message_tokens(out) == out

    # Empty / falsy passthrough.
    assert worlds_db.rewrite_initial_message_tokens("") == ""

    # Unrelated brace text untouched.
    other = "Stay safe, {hero}. The {weather} is fine."
    assert worlds_db.rewrite_initial_message_tokens(other) == other
