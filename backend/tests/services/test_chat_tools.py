"""Tests for runtime placeholder substitution in chat-side tool wrappers.

Covers feature 010 step 005: each chat-bound tool that returns
document-content text substitutes the three placeholder tokens
when ``ToolContext.runtime_placeholders`` is set, and returns
raw text when it is ``None`` (editor mode).

Tools covered:
- get_location_info
- get_npc_info
- move_to_location
- get_memory
- search        (chat-side wrapper around admin_tools.search_impl)
- get_lore      (chat-side wrapper around admin_tools.get_lore_impl)
"""

import json
from datetime import datetime, timezone

import pytest

from app.db import chats as chats_db
from app.db import locations as locations_db
from app.db import lore_facts as lore_facts_db
from app.db import npcs as npcs_db
from app.db import worlds as worlds_db
from app.models.chat_memory import ChatMemory
from app.models.chat_session import ChatSession
from app.models.world import (
    World,
    WorldLocation,
    WorldLoreFact,
    WorldNPC,
    WorldStatus,
)
from app.services import vector_storage
from app.services.chat_tools import ToolContext, build_tools
from app.services.runtime_placeholders import RuntimePlaceholderContext
from app.services.snowflake import generate_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _placeholders(
    character_name: str = "Lyra",
    location_name: str = "Crystal Cavern",
    location_summary: str = "Glowing crystals everywhere.",
) -> RuntimePlaceholderContext:
    return {
        "character_name": character_name,
        "location_name": location_name,
        "location_summary": location_summary,
    }


async def _make_world() -> int:
    world = World(
        id=generate_id(),
        name=f"tools-world-{generate_id()}",
        description="",
        lore="",
        character_template="",
        initial_message="",
        status=WorldStatus.public,
        owner_id=None,
        created_at=_now(),
        modified_at=_now(),
    )
    await worlds_db.create(world)
    return world.id


async def _make_location(world_id: int, name: str, content: str) -> int:
    loc = WorldLocation(
        id=generate_id(),
        world_id=world_id,
        name=name,
        content=content,
        created_at=_now(),
        modified_at=_now(),
    )
    await locations_db.create(loc)
    return loc.id


async def _make_npc(world_id: int, name: str, content: str) -> int:
    npc = WorldNPC(
        id=generate_id(),
        world_id=world_id,
        name=name,
        content=content,
        created_at=_now(),
        modified_at=_now(),
    )
    await npcs_db.create(npc)
    return npc.id


async def _make_session(
    world_id: int,
    current_location_id: int | None,
    character_name: str = "Lyra",
) -> int:
    session = ChatSession(
        id=generate_id(),
        user_id=generate_id(),
        world_id=world_id,
        current_location_id=current_location_id,
        character_name=character_name,
        character_description="",
        character_stats="{}",
        world_stats="{}",
        current_turn=0,
        status="active",
        created_at=_now(),
        modified_at=_now(),
    )
    saved = await chats_db.create_session(session)
    return saved.id


def _patch_vector_search(
    monkeypatch: pytest.MonkeyPatch,
    source_type: str,
    source_id: int,
) -> None:
    """Stub vector_storage.search to return one chunk pointing at source_id."""
    chunk = vector_storage.VectorChunk(
        id=str(generate_id()),
        world_id=0,
        source_type=source_type,
        source_id=source_id,
        chunk_index=0,
        text="",
        vector=[],
    )

    async def _fake_search(world_id, query, source_type=None, limit=5):
        return [chunk]

    monkeypatch.setattr(vector_storage, "search", _fake_search)


# ---------------------------------------------------------------------------
# get_location_info
# ---------------------------------------------------------------------------


async def test_get_location_info_substitutes_when_placeholders_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world_id = await _make_world()
    loc_id = await _make_location(
        world_id,
        name="Hall",
        content="Greetings {CHARACTER_NAME}, welcome to {LOCATION_NAME}.",
    )
    _patch_vector_search(monkeypatch, "location", loc_id)

    ctx = ToolContext(
        world_id=world_id,
        runtime_placeholders=_placeholders(
            character_name="Lyra", location_name="Hall",
            location_summary="ignored",
        ),
    )
    _defs, callables = build_tools(["get_location_info"], ctx)
    result = await callables["get_location_info"](query="hall")

    assert "Lyra" in result
    assert "Hall" in result
    assert "{CHARACTER_NAME}" not in result
    assert "{LOCATION_NAME}" not in result


async def test_get_location_info_raw_when_placeholders_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world_id = await _make_world()
    loc_id = await _make_location(
        world_id,
        name="Hall",
        content="Greetings {CHARACTER_NAME}, welcome to {LOCATION_NAME}.",
    )
    _patch_vector_search(monkeypatch, "location", loc_id)

    ctx = ToolContext(world_id=world_id)  # editor mode: no placeholders
    _defs, callables = build_tools(["get_location_info"], ctx)
    result = await callables["get_location_info"](query="hall")

    assert "{CHARACTER_NAME}" in result
    assert "{LOCATION_NAME}" in result


# ---------------------------------------------------------------------------
# get_npc_info
# ---------------------------------------------------------------------------


async def test_get_npc_info_substitutes_when_placeholders_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world_id = await _make_world()
    npc_id = await _make_npc(
        world_id,
        name="Old Bran",
        content="Old Bran greets {CHARACTER_NAME} in {LOCATION_NAME}.",
    )
    _patch_vector_search(monkeypatch, "npc", npc_id)

    ctx = ToolContext(
        world_id=world_id,
        runtime_placeholders=_placeholders(
            character_name="Rowan", location_name="Tavern",
            location_summary="ignored",
        ),
    )
    _defs, callables = build_tools(["get_npc_info"], ctx)
    result = await callables["get_npc_info"](query="bran")

    assert "Rowan" in result
    assert "Tavern" in result
    assert "{CHARACTER_NAME}" not in result
    assert "{LOCATION_NAME}" not in result


async def test_get_npc_info_raw_when_placeholders_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world_id = await _make_world()
    npc_id = await _make_npc(
        world_id,
        name="Old Bran",
        content="Old Bran greets {CHARACTER_NAME} in {LOCATION_NAME}.",
    )
    _patch_vector_search(monkeypatch, "npc", npc_id)

    ctx = ToolContext(world_id=world_id)
    _defs, callables = build_tools(["get_npc_info"], ctx)
    result = await callables["get_npc_info"](query="bran")

    assert "{CHARACTER_NAME}" in result
    assert "{LOCATION_NAME}" in result


# ---------------------------------------------------------------------------
# move_to_location
# ---------------------------------------------------------------------------


async def test_move_to_location_substitutes_when_placeholders_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world_id = await _make_world()
    starting_id = await _make_location(world_id, "Starting Hall", "start")
    dest_id = await _make_location(
        world_id,
        name="Crystal Cavern",
        content="Hello {CHARACTER_NAME}, you reach {LOCATION_NAME}.",
    )
    session_id = await _make_session(
        world_id, current_location_id=starting_id, character_name="Tessa",
    )
    _patch_vector_search(monkeypatch, "location", dest_id)

    ctx = ToolContext(
        world_id=world_id,
        session_id=session_id,
        runtime_placeholders=_placeholders(
            character_name="Tessa", location_name="Crystal Cavern",
            location_summary="ignored",
        ),
    )
    _defs, callables = build_tools(["move_to_location"], ctx)
    result = await callables["move_to_location"](location_name="Crystal Cavern")

    payload = json.loads(result)
    assert payload["status"] == "OK"
    assert "Tessa" in payload["location"]["description"]
    assert "Crystal Cavern" in payload["location"]["description"]
    assert "{CHARACTER_NAME}" not in result
    assert "{LOCATION_NAME}" not in result


async def test_move_to_location_raw_when_placeholders_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world_id = await _make_world()
    starting_id = await _make_location(world_id, "Starting Hall", "start")
    dest_id = await _make_location(
        world_id,
        name="Crystal Cavern",
        content="Hello {CHARACTER_NAME}, you reach {LOCATION_NAME}.",
    )
    session_id = await _make_session(
        world_id, current_location_id=starting_id, character_name="Tessa",
    )
    _patch_vector_search(monkeypatch, "location", dest_id)

    ctx = ToolContext(world_id=world_id, session_id=session_id)
    _defs, callables = build_tools(["move_to_location"], ctx)
    result = await callables["move_to_location"](location_name="Crystal Cavern")

    payload = json.loads(result)
    assert payload["status"] == "OK"
    assert "{CHARACTER_NAME}" in payload["location"]["description"]
    assert "{LOCATION_NAME}" in payload["location"]["description"]


# ---------------------------------------------------------------------------
# get_memory
# ---------------------------------------------------------------------------


async def test_get_memory_substitutes_when_placeholders_set() -> None:
    world_id = await _make_world()
    session_id = await _make_session(
        world_id, current_location_id=None, character_name="Quill",
    )

    mem = ChatMemory(
        id=generate_id(),
        session_id=session_id,
        content="Recall: {CHARACTER_NAME} once visited {LOCATION_NAME}.",
        created_at=_now(),
    )
    await chats_db.create_memory(mem)

    ctx = ToolContext(
        session_id=session_id,
        runtime_placeholders=_placeholders(
            character_name="Quill", location_name="Old Mill",
            location_summary="ignored",
        ),
    )
    _defs, callables = build_tools(["get_memory"], ctx)
    result = await callables["get_memory"]()

    assert "Quill" in result
    assert "Old Mill" in result
    assert "{CHARACTER_NAME}" not in result
    assert "{LOCATION_NAME}" not in result


async def test_get_memory_raw_when_placeholders_none() -> None:
    world_id = await _make_world()
    session_id = await _make_session(
        world_id, current_location_id=None, character_name="Quill",
    )

    mem = ChatMemory(
        id=generate_id(),
        session_id=session_id,
        content="Recall: {CHARACTER_NAME} once visited {LOCATION_NAME}.",
        created_at=_now(),
    )
    await chats_db.create_memory(mem)

    ctx = ToolContext(session_id=session_id)
    _defs, callables = build_tools(["get_memory"], ctx)
    result = await callables["get_memory"]()

    assert "{CHARACTER_NAME}" in result
    assert "{LOCATION_NAME}" in result


# ---------------------------------------------------------------------------
# search (chat-side wrapper)
# ---------------------------------------------------------------------------


async def test_search_substitutes_when_placeholders_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world_id = await _make_world()
    loc_id = await _make_location(
        world_id,
        name="Hall",
        content="Hi {CHARACTER_NAME} in {LOCATION_NAME}.",
    )
    _patch_vector_search(monkeypatch, "location", loc_id)

    ctx = ToolContext(
        world_id=world_id,
        runtime_placeholders=_placeholders(
            character_name="Aria", location_name="Hall",
            location_summary="ignored",
        ),
    )
    _defs, callables = build_tools(["search"], ctx)
    result = await callables["search"](query="anything")

    assert "Aria" in result
    assert "{CHARACTER_NAME}" not in result
    assert "{LOCATION_NAME}" not in result


async def test_search_raw_when_placeholders_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world_id = await _make_world()
    loc_id = await _make_location(
        world_id,
        name="Hall",
        content="Hi {CHARACTER_NAME} in {LOCATION_NAME}.",
    )
    _patch_vector_search(monkeypatch, "location", loc_id)

    ctx = ToolContext(world_id=world_id)
    _defs, callables = build_tools(["search"], ctx)
    result = await callables["search"](query="anything")

    assert "{CHARACTER_NAME}" in result
    assert "{LOCATION_NAME}" in result


# ---------------------------------------------------------------------------
# get_lore (chat-side wrapper)
# ---------------------------------------------------------------------------


async def test_get_lore_substitutes_when_placeholders_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world_id = await _make_world()
    fact = WorldLoreFact(
        id=generate_id(),
        world_id=world_id,
        content="Legend says {CHARACTER_NAME} once stood in {LOCATION_NAME}.",
        is_injected=False,
        weight=0,
        created_at=_now(),
        modified_at=_now(),
    )
    await lore_facts_db.create(fact)
    _patch_vector_search(monkeypatch, "lore_fact", fact.id)

    ctx = ToolContext(
        world_id=world_id,
        runtime_placeholders=_placeholders(
            character_name="Idris", location_name="Stoneholm",
            location_summary="ignored",
        ),
    )
    _defs, callables = build_tools(["get_lore"], ctx)
    result = await callables["get_lore"](query="legend")

    assert "Idris" in result
    assert "Stoneholm" in result
    assert "{CHARACTER_NAME}" not in result
    assert "{LOCATION_NAME}" not in result


async def test_get_lore_raw_when_placeholders_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world_id = await _make_world()
    fact = WorldLoreFact(
        id=generate_id(),
        world_id=world_id,
        content="Legend says {CHARACTER_NAME} once stood in {LOCATION_NAME}.",
        is_injected=False,
        weight=0,
        created_at=_now(),
        modified_at=_now(),
    )
    await lore_facts_db.create(fact)
    _patch_vector_search(monkeypatch, "lore_fact", fact.id)

    ctx = ToolContext(world_id=world_id)
    _defs, callables = build_tools(["get_lore"], ctx)
    result = await callables["get_lore"](query="legend")

    assert "{CHARACTER_NAME}" in result
    assert "{LOCATION_NAME}" in result
