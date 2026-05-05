"""Tests for `chat_service.create_chat` runtime substitution of the
uppercase placeholder tokens in `world.initial_message`."""

import json
from datetime import datetime, timezone

import pytest

from app.db import chats as chats_db
from app.db import locations as locations_db
from app.db import worlds as worlds_db
from app.models.schemas.chat import ModelConfig
from app.models.world import World, WorldLocation, WorldStatus
from app.services import chat_service, vector_storage
from app.services.chat_tools import ToolContext, build_tools
from app.services.runtime_placeholders import RuntimePlaceholderContext
from app.services.snowflake import generate_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _setup_world_and_location(initial_message: str) -> tuple[int, int, str, str]:
    """Create a public world and a starting location. Returns
    (world_id, location_id, location_name, location_content)."""
    location_name = f"Loc-{generate_id()}"
    location_content = "A quiet stone hall lit by torches."

    world = World(
        id=generate_id(),
        name=f"chat-test-world-{generate_id()}",
        description="",
        lore="",
        character_template="",
        initial_message=initial_message,
        status=WorldStatus.public,
        owner_id=None,
        created_at=_now(),
        modified_at=_now(),
    )
    await worlds_db.create(world)

    loc = WorldLocation(
        id=generate_id(),
        world_id=world.id,
        name=location_name,
        content=location_content,
        created_at=_now(),
        modified_at=_now(),
    )
    await locations_db.create(loc)

    return world.id, loc.id, location_name, location_content


def _empty_model_config() -> ModelConfig:
    return ModelConfig(model_id=None, temperature=0.7, repeat_penalty=1.0, top_p=1.0)


async def test_create_chat_substitutes_uppercase_tokens() -> None:
    template = (
        "Welcome, {CHARACTER_NAME}. You arrive at {LOCATION_NAME}. "
        "{LOCATION_SUMMARY}"
    )
    world_id, loc_id, loc_name, loc_content = await _setup_world_and_location(template)

    user_id = generate_id()
    character_name = "Aelric"

    resp = await chat_service.create_chat(
        world_id=world_id,
        user_id=user_id,
        character_name=character_name,
        template_variables={},
        starting_location_id=loc_id,
        tool_model=_empty_model_config(),
        text_model=_empty_model_config(),
    )

    messages = await chats_db.list_active_messages(int(resp.id))
    system_msgs = [m for m in messages if m.role == "system"]
    assert len(system_msgs) == 1
    content = system_msgs[0].content

    assert character_name in content
    assert loc_name in content
    assert loc_content in content
    assert "{CHARACTER_NAME}" not in content
    assert "{LOCATION_NAME}" not in content
    assert "{LOCATION_SUMMARY}" not in content


async def test_create_chat_does_not_substitute_lowercase_tokens() -> None:
    """The runtime layer recognizes uppercase tokens only — lowercase
    survives untouched (the migration is the only path that should
    rewrite token shapes)."""
    template = (
        "Welcome, {character_name}. You arrive at {location_name}. "
        "{location_summary}"
    )
    world_id, loc_id, _loc_name, _loc_content = await _setup_world_and_location(template)

    user_id = generate_id()
    character_name = "Brynn"

    resp = await chat_service.create_chat(
        world_id=world_id,
        user_id=user_id,
        character_name=character_name,
        template_variables={},
        starting_location_id=loc_id,
        tool_model=_empty_model_config(),
        text_model=_empty_model_config(),
    )

    messages = await chats_db.list_active_messages(int(resp.id))
    system_msgs = [m for m in messages if m.role == "system"]
    assert len(system_msgs) == 1
    content = system_msgs[0].content

    # Lowercase tokens are NOT recognized at runtime.
    assert "{character_name}" in content
    assert "{location_name}" in content
    assert "{location_summary}" in content
    # And the character_name value was therefore not substituted in.
    assert character_name not in content


# ---------------------------------------------------------------------------
# End-to-end: move_to_location substitutes {CHARACTER_NAME} in destination.
# ---------------------------------------------------------------------------


async def test_move_to_location_end_to_end_substitutes_character_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A chat session created via `create_chat` then moved (via the
    bound `move_to_location` tool) into a destination whose `content`
    contains `{CHARACTER_NAME}` produces a player-visible JSON payload
    with the character name substituted in.

    Mirrors how `chain_generation_service` / `simple_generation_service`
    construct the chat-bound `ToolContext` and dispatch the tool.
    """
    starting_content = "A quiet starting hall."
    destination_name = f"Cavern-{generate_id()}"
    destination_content = (
        "Welcome, {CHARACTER_NAME}. You have entered {LOCATION_NAME}."
    )

    world_id, starting_loc_id, _start_name, _start_content = (
        await _setup_world_and_location("ignored initial message")
    )

    # Add a destination location reachable via the move tool.
    dest = WorldLocation(
        id=generate_id(),
        world_id=world_id,
        name=destination_name,
        content=destination_content,
        created_at=_now(),
        modified_at=_now(),
    )
    await locations_db.create(dest)

    user_id = generate_id()
    character_name = "Cordelia"

    resp = await chat_service.create_chat(
        world_id=world_id,
        user_id=user_id,
        character_name=character_name,
        template_variables={},
        starting_location_id=starting_loc_id,
        tool_model=_empty_model_config(),
        text_model=_empty_model_config(),
    )
    session_id = int(resp.id)

    # Mirror the chat-runtime ToolContext that generation services build.
    runtime_placeholders: RuntimePlaceholderContext = {
        "character_name": character_name,
        "location_name": destination_name,
        "location_summary": destination_content,
    }
    ctx = ToolContext(
        world_id=world_id,
        session_id=session_id,
        runtime_placeholders=runtime_placeholders,
    )

    # Stub vector search to point at the destination row.
    chunk = vector_storage.VectorChunk(
        id=str(generate_id()),
        world_id=world_id,
        source_type="location",
        source_id=dest.id,
        chunk_index=0,
        text="",
        vector=[],
    )

    async def _fake_search(world_id, query, source_type=None, limit=5):
        return [chunk]

    monkeypatch.setattr(vector_storage, "search", _fake_search)

    _defs, callables = build_tools(["move_to_location"], ctx)
    raw = await callables["move_to_location"](location_name=destination_name)

    payload = json.loads(raw)
    assert payload["status"] == "OK"
    assert character_name in payload["location"]["description"]
    assert destination_name in payload["location"]["description"]
    assert "{CHARACTER_NAME}" not in raw
    assert "{LOCATION_NAME}" not in raw

    # Session's current_location_id was updated to the destination.
    refreshed = await chats_db.get_session_by_id(session_id)
    assert refreshed is not None
    assert refreshed.current_location_id == dest.id
