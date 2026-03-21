"""Context builder for rich chat system prompts.

PURPOSE
    Loads all world/session data needed for the rich system prompt and
    formats each piece into human-readable strings suitable for prompt injection.

USAGE
    Called by simple_generation_service and chain_generation_service
    before building system prompts.

DESIGN RATIONALE
    Centralized context loading avoids duplication across generation modes.
    TypedDict return type ensures strict typing without Pydantic overhead.

CHANGELOG
    stage3_step2a — Created
"""

import json
import logging
from typing import Any, TypedDict

from app.db import chats as chats_db
from app.db import locations as locations_db
from app.db import lore_facts as lore_facts_db
from app.db import npc_links as npc_links_db
from app.db import npcs as npcs_db
from app.db import rules as rules_db
from app.db import stat_defs as stat_defs_db
from app.db import worlds as worlds_db
from app.models.chat_session import ChatSession
from app.models.world import World, WorldStatDefinition

logger = logging.getLogger(__name__)


class ChatContext(TypedDict):
    world: World
    location_name: str
    location_description: str
    location_exits: str
    present_npcs: str
    rules: str
    stat_definitions: str
    current_stats: str
    injected_lore: str
    memories: str
    stat_defs_list: list[WorldStatDefinition]


async def build_chat_context(session: ChatSession) -> ChatContext:
    """Load all context needed for system prompt. Formats into strings."""
    world = await worlds_db.get_by_id(session.world_id)
    if world is None:
        raise ValueError(f"World {session.world_id} not found")

    # Location
    location_name = ""
    location_description = ""
    location_exits = ""
    if session.current_location_id:
        location = await locations_db.get_by_id(session.current_location_id)
        if location:
            location_name = location.name
            location_description = location.content
            location_exits = await _format_exits(location.exits)

    # NPCs at location
    present_npcs = ""
    if session.current_location_id:
        present_npcs = await _format_npcs_at_location(session.current_location_id)

    # Rules
    rules_list = await rules_db.list_by_world(session.world_id)
    rules = "\n".join(f"{i}. {r.rule_text}" for i, r in enumerate(rules_list, 1)) if rules_list else ""

    # Stat definitions
    stat_defs = await stat_defs_db.list_by_world(session.world_id)
    stat_definitions = _format_stat_definitions(stat_defs)

    # Current stats
    char_stats = chats_db.parse_stats(session.character_stats)
    world_stats_dict = chats_db.parse_stats(session.world_stats)
    current_stats = _format_current_stats(char_stats, world_stats_dict, stat_defs)

    # Injected lore
    injected_facts = await lore_facts_db.list_injected_by_world(session.world_id)
    injected_lore = "\n---\n".join(f.content for f in injected_facts) if injected_facts else ""

    # Memories
    memories_list = await chats_db.list_memories(session.id)
    memories = "\n---\n".join(m.content for m in memories_list) if memories_list else ""

    return ChatContext(
        world=world,
        location_name=location_name,
        location_description=location_description,
        location_exits=location_exits,
        present_npcs=present_npcs,
        rules=rules,
        stat_definitions=stat_definitions,
        current_stats=current_stats,
        injected_lore=injected_lore,
        memories=memories,
        stat_defs_list=stat_defs,
    )


async def _format_exits(exits_json: str | None) -> str:
    """Resolve exit location IDs to names."""
    if not exits_json:
        return ""
    try:
        exit_ids = json.loads(exits_json)
    except json.JSONDecodeError:
        return ""
    if not isinstance(exit_ids, list):
        return ""

    names: list[str] = []
    for eid in exit_ids:
        loc = await locations_db.get_by_id(int(eid))
        if loc:
            names.append(loc.name)
    return ", ".join(names)


async def _format_npcs_at_location(location_id: int) -> str:
    """Load NPCs present at a location via npc_location_links."""
    links = await npc_links_db.list_by_location(location_id)
    present_links = [lnk for lnk in links if lnk.link_type.value == "present"]
    if not present_links:
        return ""

    parts: list[str] = []
    for link in present_links:
        npc = await npcs_db.get_by_id(link.npc_id)
        if npc:
            # Use first paragraph as brief description
            brief = npc.content.split("\n\n")[0] if npc.content else ""
            parts.append(f"- **{npc.name}**: {brief}")
    return "\n".join(parts)


def _format_stat_definitions(stat_defs: list[WorldStatDefinition]) -> str:
    """Format stat definitions with type and constraints."""
    if not stat_defs:
        return ""

    parts: list[str] = []
    for sd in stat_defs:
        line = f"- **{sd.name}** ({sd.stat_type.value}, {sd.scope.value}): {sd.description}"
        constraints: list[str] = []
        if sd.stat_type.value == "int":
            if sd.min_value is not None:
                constraints.append(f"min={sd.min_value}")
            if sd.max_value is not None:
                constraints.append(f"max={sd.max_value}")
        if sd.enum_values:
            try:
                vals = json.loads(sd.enum_values)
                constraints.append(f"values={vals}")
            except json.JSONDecodeError:
                pass
        if constraints:
            line += f" [{', '.join(constraints)}]"
        if sd.hidden:
            line += " (hidden from player)"
        parts.append(line)
    return "\n".join(parts)


def _format_current_stats(
    char_stats: dict[str, Any],
    world_stats: dict[str, Any],
    stat_defs: list[WorldStatDefinition],
) -> str:
    """Format current stat values grouped by scope."""
    if not char_stats and not world_stats:
        return ""

    parts: list[str] = []
    if char_stats:
        parts.append("Character stats:")
        for name, value in char_stats.items():
            parts.append(f"  {name}: {value}")
    if world_stats:
        parts.append("World stats:")
        for name, value in world_stats.items():
            parts.append(f"  {name}: {value}")
    return "\n".join(parts)
