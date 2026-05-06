"""Tests for runtime placeholder substitution in `build_chat_context`.

Covers the three substitution sites added in feature 010 step 004:
- WorldLocation.content
- WorldLoreFact.content (is_injected=True)
- WorldNPC content brief (first paragraph)

All resolve against the session's **current** location (not the
starting location), per the feature 010 expansion decision.
"""

import json
from datetime import datetime, timezone

from app.db import chats as chats_db
from app.db import locations as locations_db
from app.db import lore_facts as lore_facts_db
from app.db import npc_links as npc_links_db
from app.db import npcs as npcs_db
from app.db import stat_defs as stat_defs_db
from app.db import worlds as worlds_db
from app.models.chat_session import ChatSession
from app.models.world import (
    NPCLinkType,
    NPCLocationLink,
    StatScope,
    StatType,
    World,
    WorldLocation,
    WorldLoreFact,
    WorldNPC,
    WorldStatDefinition,
    WorldStatus,
)
from app.services.chat_context import build_chat_context
from app.services.runtime_placeholders import apply_runtime_placeholders
from app.services.snowflake import generate_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _make_world() -> int:
    world = World(
        id=generate_id(),
        name=f"ctx-world-{generate_id()}",
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


async def _make_session(
    world_id: int,
    current_location_id: int,
    character_name: str,
) -> ChatSession:
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
    return await chats_db.create_session(session)


# ── Location.content substitution ────────────────────────────────────


async def test_location_content_uses_current_location_placeholders() -> None:
    """The session's current location's content is substituted using
    the **current** location's name (not the starting location)."""
    world_id = await _make_world()

    # A starting location the player is no longer at -- proves we use
    # current, not starting.
    _starting_loc_id = await _make_location(world_id, "Starting Hall", "ignored")

    current_loc_id = await _make_location(
        world_id,
        name="Crystal Cavern",
        content=(
            "{CHARACTER_NAME} stands within {LOCATION_NAME}, listening to "
            "the echoes."
        ),
    )

    character_name = "Tessa"
    session = await _make_session(world_id, current_loc_id, character_name)

    ctx = await build_chat_context(session)

    assert "Tessa" in ctx["location_description"]
    assert "Crystal Cavern" in ctx["location_description"]
    assert "{CHARACTER_NAME}" not in ctx["location_description"]
    assert "{LOCATION_NAME}" not in ctx["location_description"]
    # location_name itself is unchanged.
    assert ctx["location_name"] == "Crystal Cavern"


# ── Injected lore fact substitution ──────────────────────────────────


async def test_injected_lore_substitutes_placeholders() -> None:
    world_id = await _make_world()
    current_loc_id = await _make_location(
        world_id, name="Riverbend", content="A bend in the river.",
    )

    fact = WorldLoreFact(
        id=generate_id(),
        world_id=world_id,
        content=(
            "Travelers say {LOCATION_NAME} was founded by an exile."
        ),
        is_injected=True,
        weight=0,
        created_at=_now(),
        modified_at=_now(),
    )
    await lore_facts_db.create(fact)

    session = await _make_session(world_id, current_loc_id, "Mira")
    ctx = await build_chat_context(session)

    assert "Riverbend" in ctx["injected_lore"]
    assert "{LOCATION_NAME}" not in ctx["injected_lore"]


# ── NPC brief substitution ───────────────────────────────────────────


async def test_npc_brief_substitutes_placeholders() -> None:
    world_id = await _make_world()
    current_loc_id = await _make_location(
        world_id, name="Tavern", content="A cozy tavern.",
    )

    npc = WorldNPC(
        id=generate_id(),
        world_id=world_id,
        name="Old Bran",
        content=(
            "Old Bran greets {CHARACTER_NAME} with a wave.\n\n"
            "Background details that should not appear in the brief."
        ),
        created_at=_now(),
        modified_at=_now(),
    )
    await npcs_db.create(npc)

    link = NPCLocationLink(
        id=generate_id(),
        npc_id=npc.id,
        location_id=current_loc_id,
        link_type=NPCLinkType.present,
    )
    await npc_links_db.create(link)

    session = await _make_session(world_id, current_loc_id, "Rowan")
    ctx = await build_chat_context(session)

    assert "Rowan" in ctx["present_npcs"]
    assert "Old Bran" in ctx["present_npcs"]
    assert "{CHARACTER_NAME}" not in ctx["present_npcs"]
    # Only the first paragraph is the brief; the second should not
    # leak in.
    assert "Background details" not in ctx["present_npcs"]


# ── Feature 012 step 002: stat snapshots on ChatContext ──────────────


async def _make_stat_def(
    *, world_id: int, name: str, scope: StatScope, stat_type: StatType,
    enum_values: list[str] | None = None, hidden: bool = False,
) -> WorldStatDefinition:
    sd = WorldStatDefinition(
        id=generate_id(),
        world_id=world_id,
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
    return await stat_defs_db.create(sd)


async def test_build_chat_context_exposes_raw_stat_dicts() -> None:
    """The new raw fields must surface the parsed JSON stat dicts so
    downstream chat-runtime callers don't re-parse from ChatSession."""
    world_id = await _make_world()
    loc_id = await _make_location(world_id, "Hall", "A hall.")

    await _make_stat_def(
        world_id=world_id, name="HEALTH",
        scope=StatScope.character, stat_type=StatType.int_,
    )
    await _make_stat_def(
        world_id=world_id, name="MOOD",
        scope=StatScope.character, stat_type=StatType.enum_,
        enum_values=["calm", "angry"],
    )
    await _make_stat_def(
        world_id=world_id, name="TAGS",
        scope=StatScope.character, stat_type=StatType.set_,
        enum_values=["alpha", "beta", "gamma"],
    )
    await _make_stat_def(
        world_id=world_id, name="SECRET",
        scope=StatScope.character, stat_type=StatType.int_,
        hidden=True,
    )
    await _make_stat_def(
        world_id=world_id, name="WEATHER",
        scope=StatScope.world, stat_type=StatType.enum_,
        enum_values=["sunny", "rainy"],
    )

    session = ChatSession(
        id=generate_id(),
        user_id=generate_id(),
        world_id=world_id,
        current_location_id=loc_id,
        character_name="Aelric",
        character_description="",
        character_stats=json.dumps({
            "HEALTH": 42, "MOOD": "calm", "TAGS": ["beta"], "SECRET": 7,
        }),
        world_stats=json.dumps({"WEATHER": "rainy"}),
        current_turn=0,
        status="active",
        created_at=_now(),
        modified_at=_now(),
    )
    await chats_db.create_session(session)

    ctx = await build_chat_context(session)

    assert ctx["character_stats_raw"] == {
        "HEALTH": 42, "MOOD": "calm", "TAGS": ["beta"], "SECRET": 7,
    }
    assert ctx["world_stats_raw"] == {"WEATHER": "rainy"}
    # The definitions list should include all five (declared order may
    # vary across DB backends; assert the names instead of position).
    names = {d.name for d in ctx["stat_defs_list"]}
    assert {"HEALTH", "MOOD", "TAGS", "SECRET", "WEATHER"} <= names


async def test_build_chat_context_substitutes_user_stat_in_location() -> None:
    """A {USER:HEALTH} token in a location's content must resolve to
    the chat's stored HEALTH value via the chat-runtime build path."""
    world_id = await _make_world()
    loc_id = await _make_location(
        world_id, "Hall",
        "{CHARACTER_NAME} reports HP={USER:HEALTH} weather={WORLD:WEATHER}.",
    )
    await _make_stat_def(
        world_id=world_id, name="HEALTH",
        scope=StatScope.character, stat_type=StatType.int_,
    )
    await _make_stat_def(
        world_id=world_id, name="WEATHER",
        scope=StatScope.world, stat_type=StatType.enum_,
        enum_values=["sunny", "rainy"],
    )

    session = ChatSession(
        id=generate_id(),
        user_id=generate_id(),
        world_id=world_id,
        current_location_id=loc_id,
        character_name="Aelric",
        character_description="",
        character_stats=json.dumps({"HEALTH": 88}),
        world_stats=json.dumps({"WEATHER": "rainy"}),
        current_turn=0,
        status="active",
        created_at=_now(),
        modified_at=_now(),
    )
    await chats_db.create_session(session)

    ctx = await build_chat_context(session)

    assert "HP=88" in ctx["location_description"]
    assert "weather=rainy" in ctx["location_description"]
    assert "Aelric" in ctx["location_description"]
    assert "{USER:HEALTH}" not in ctx["location_description"]
    assert "{WORLD:WEATHER}" not in ctx["location_description"]


async def test_editor_path_leaves_namespaced_token_literal() -> None:
    """Editor analogue: passing None as runtime ctx must leave
    `{USER:HEALTH}` untouched (editor LLMs see the literal token so
    they learn the syntax). No ChatContext involved here -- this
    asserts the cross-cutting editor-mode contract that step 002
    must not regress."""
    text = "Watch HP={USER:HEALTH} carefully."
    assert apply_runtime_placeholders(text, None) == text
