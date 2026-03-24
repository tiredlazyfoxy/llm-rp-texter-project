"""Chat tools — player-facing in-game tools for all generation modes.

PURPOSE
    Eight tools available to the LLM during chat generation.
    Reuses admin_tools search/lore/web implementations. Adds location/NPC
    info lookup, location movement, and session memory management.

USAGE
    get_chat_tools(world_id, session_id) -> (tool_definitions, {name: callable})
    Callables are passed directly to client.chat_with_tools().

CHANGELOG
    stage3_step2a — Created
"""

import functools
import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from llm import pydantic_to_openai_tool

from app.services import admin_tools

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parameter schemas
# ---------------------------------------------------------------------------

class GetLocationInfoParams(BaseModel):
    query: str


class GetNpcInfoParams(BaseModel):
    query: str


class SearchParams(BaseModel):
    query: str
    source_type: str | None = None


class GetLoreParams(BaseModel):
    query: str


class WebSearchParams(BaseModel):
    query: str


class GetMemoryParams(BaseModel):
    pass


class AddMemoryParams(BaseModel):
    content: str


class MoveToLocationParams(BaseModel):
    location_name: str


# Planning-only param schemas
class AddFactParams(BaseModel):
    content: str


class AddDecisionParams(BaseModel):
    content: str


class UpdateStatParams(BaseModel):
    name: str
    value: str


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling format)
# ---------------------------------------------------------------------------

CHAT_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    pydantic_to_openai_tool(
        "get_location_info",
        (
            "Look up detailed information about a location in the world. "
            "Returns the full location description, exits, and NPCs present there."
        ),
        GetLocationInfoParams,
    ),
    pydantic_to_openai_tool(
        "get_npc_info",
        (
            "Look up detailed information about an NPC in the world. "
            "Returns the full NPC description and their known locations."
        ),
        GetNpcInfoParams,
    ),
    pydantic_to_openai_tool(
        "search",
        (
            "Search world knowledge by semantic similarity. "
            "Returns matching documents (locations, NPCs, or lore facts). "
            "Use source_type to filter: 'location', 'npc', or 'lore_fact'."
        ),
        SearchParams,
    ),
    pydantic_to_openai_tool(
        "get_lore",
        (
            "Find the most relevant lore fact for a query. "
            "Returns the full text of the best matching lore entry."
        ),
        GetLoreParams,
    ),
    pydantic_to_openai_tool(
        "web_search",
        (
            "Search the web for real-world information not in the world documents. "
            "Returns titles, URLs, and snippets."
        ),
        WebSearchParams,
    ),
    pydantic_to_openai_tool(
        "get_memory",
        "Retrieve all saved memories for this session.",
        GetMemoryParams,
    ),
    pydantic_to_openai_tool(
        "add_memory",
        (
            "Save an important fact or observation to session memory "
            "for future reference."
        ),
        AddMemoryParams,
    ),
    pydantic_to_openai_tool(
        "move_to_location",
        (
            "Move the player to a different location. Use the exact location name "
            "as shown in exits or search results. Returns the new location's "
            "description, exits, and NPCs present."
        ),
        MoveToLocationParams,
    ),
]


PLANNING_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    pydantic_to_openai_tool(
        "add_fact",
        (
            "Record a relevant observation or piece of context that the writing "
            "agent needs to craft the narrative. Call once per distinct fact."
        ),
        AddFactParams,
    ),
    pydantic_to_openai_tool(
        "add_decision",
        (
            "Record a specific plot point, action outcome, or NPC reaction "
            "for this turn. The writing agent will follow these faithfully."
        ),
        AddDecisionParams,
    ),
    pydantic_to_openai_tool(
        "update_stat",
        (
            "Update a stat value. Validated immediately — you will get an error "
            "message if the stat name or value is invalid, and can retry."
        ),
        UpdateStatParams,
    ),
]


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------

async def get_location_info_impl(world_id: int, query: str) -> str:
    """Vector search scoped to locations, return full doc + exits + linked NPCs."""
    from app.db import locations as locations_db
    from app.db import npc_links as npc_links_db
    from app.db import npcs as npcs_db
    from app.services import vector_storage

    chunks = await vector_storage.search(world_id, query, source_type="location", limit=3)
    if not chunks:
        return "No location found matching that query."

    # Use first unique match
    seen: set[int] = set()
    for chunk in chunks:
        if chunk.source_id in seen:
            continue
        seen.add(chunk.source_id)

        location = await locations_db.get_by_id(chunk.source_id)
        if not location:
            continue

        parts = [f"**Location: {location.name}**\n\n{location.content}"]

        # Exits
        if location.exits:
            try:
                exit_ids = json.loads(location.exits)
                exit_names: list[str] = []
                for eid in exit_ids:
                    loc = await locations_db.get_by_id(int(eid))
                    if loc:
                        exit_names.append(loc.name)
                if exit_names:
                    parts.append(f"**Exits:** {', '.join(exit_names)}")
            except (json.JSONDecodeError, ValueError):
                pass

        # Linked NPCs
        links = await npc_links_db.list_by_location(location.id)
        present_npcs = [lnk for lnk in links if lnk.link_type.value == "present"]
        if present_npcs:
            npc_parts: list[str] = []
            for link in present_npcs:
                npc = await npcs_db.get_by_id(link.npc_id)
                if npc:
                    brief = npc.content.split("\n\n")[0] if npc.content else ""
                    npc_parts.append(f"- {npc.name}: {brief}")
            if npc_parts:
                parts.append("**NPCs here:**\n" + "\n".join(npc_parts))

        return "\n\n".join(parts)

    return "No location found matching that query."


async def get_npc_info_impl(world_id: int, query: str) -> str:
    """Vector search scoped to NPCs, return full doc + location links."""
    from app.db import locations as locations_db
    from app.db import npc_links as npc_links_db
    from app.db import npcs as npcs_db
    from app.services import vector_storage

    chunks = await vector_storage.search(world_id, query, source_type="npc", limit=3)
    if not chunks:
        return "No NPC found matching that query."

    seen: set[int] = set()
    for chunk in chunks:
        if chunk.source_id in seen:
            continue
        seen.add(chunk.source_id)

        npc = await npcs_db.get_by_id(chunk.source_id)
        if not npc:
            continue

        parts = [f"**NPC: {npc.name}**\n\n{npc.content}"]

        # Location links
        links = await npc_links_db.list_by_npc(npc.id)
        if links:
            loc_parts: list[str] = []
            for link in links:
                loc = await locations_db.get_by_id(link.location_id)
                if loc:
                    link_desc = "present" if link.link_type.value == "present" else "excluded"
                    loc_parts.append(f"- {loc.name} ({link_desc})")
            if loc_parts:
                parts.append("**Locations:**\n" + "\n".join(loc_parts))

        return "\n\n".join(parts)

    return "No NPC found matching that query."


async def get_memory_impl(session_id: int) -> str:
    """Return all session memories concatenated."""
    from app.db import chats as chats_db

    memories = await chats_db.list_memories(session_id)
    if not memories:
        return "No memories recorded."
    return "\n---\n".join(m.content for m in memories)


async def add_memory_impl(session_id: int, content: str) -> str:
    """Create a new ChatMemory record."""
    from app.db import chats as chats_db
    from app.models.chat_memory import ChatMemory
    from app.services import snowflake as snowflake_svc

    memory = ChatMemory(
        id=snowflake_svc.generate_id(),
        session_id=session_id,
        content=content,
        created_at=datetime.now(timezone.utc),
    )
    await chats_db.create_memory(memory)
    return "Memory saved."


async def move_to_location_impl(world_id: int, session_id: int, location_name: str) -> str:
    """Resolve location name → ID, update session, return new location info."""
    from app.db import chats as chats_db
    from app.db import locations as locations_db
    from app.db import npc_links as npc_links_db
    from app.db import npcs as npcs_db
    from app.services import vector_storage

    # Vector search to resolve location name
    location = None
    chunks = await vector_storage.search(world_id, location_name, source_type="location", limit=1)
    if chunks:
        location = await locations_db.get_by_id(chunks[0].source_id)

    if location is None:
        return f"Location '{location_name}' not found in this world."

    # Update session
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None:
        return "Session not found."
    chat.current_location_id = location.id
    chat.modified_at = datetime.now(timezone.utc)
    await chats_db.update_session(chat)

    # Format response (same as get_location_info_impl)
    parts = [f"**Moved to: {location.name}**\n\n{location.content}"]

    if location.exits:
        try:
            exit_ids = json.loads(location.exits)
            exit_names: list[str] = []
            for eid in exit_ids:
                loc = await locations_db.get_by_id(int(eid))
                if loc:
                    exit_names.append(loc.name)
            if exit_names:
                parts.append(f"**Exits:** {', '.join(exit_names)}")
        except (json.JSONDecodeError, ValueError):
            pass

    links = await npc_links_db.list_by_location(location.id)
    present_npcs = [lnk for lnk in links if lnk.link_type.value == "present"]
    if present_npcs:
        npc_parts: list[str] = []
        for link in present_npcs:
            npc = await npcs_db.get_by_id(link.npc_id)
            if npc:
                brief = npc.content.split("\n\n")[0] if npc.content else ""
                npc_parts.append(f"- {npc.name}: {brief}")
        if npc_parts:
            parts.append("**NPCs here:**\n" + "\n".join(npc_parts))

    logger.info("Player moved to '%s' (id=%d) in session %d", location.name, location.id, session_id)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

async def _get_injected_ids(world_id: int) -> set[int]:
    """Return IDs of lore facts always injected into context."""
    from app.db import lore_facts
    facts = await lore_facts.list_injected_by_world(world_id)
    return {f.id for f in facts}


def get_chat_tools(
    world_id: int, session_id: int,
) -> tuple[list[dict[str, Any]], dict[str, Callable]]:
    """Return (tool_definitions, {name: async_callable}) bound to world and session."""

    async def get_location_info(query: str) -> str:
        return await get_location_info_impl(world_id, query)

    async def get_npc_info(query: str) -> str:
        return await get_npc_info_impl(world_id, query)

    async def search(query: str, source_type: str | None = None) -> str:
        injected_ids = await _get_injected_ids(world_id)
        return await admin_tools.search_impl(world_id, query, source_type, injected_ids)

    async def get_lore(query: str) -> str:
        injected_ids = await _get_injected_ids(world_id)
        return await admin_tools.get_lore_impl(world_id, query, injected_ids)

    async def web_search(query: str) -> str:
        return await admin_tools.web_search_impl(query)

    async def get_memory() -> str:
        return await get_memory_impl(session_id)

    async def add_memory(content: str) -> str:
        return await add_memory_impl(session_id, content)

    async def move_to_location(location_name: str) -> str:
        return await move_to_location_impl(world_id, session_id, location_name)

    # functools.wraps preserves signatures for chat_with_tools inspect.signature()
    callables: dict[str, Callable] = {
        "get_location_info": functools.wraps(get_location_info_impl)(get_location_info),
        "get_npc_info": functools.wraps(get_npc_info_impl)(get_npc_info),
        "search": functools.wraps(admin_tools.search_impl)(search),
        "get_lore": functools.wraps(admin_tools.get_lore_impl)(get_lore),
        "web_search": functools.wraps(admin_tools.web_search_impl)(web_search),
        "get_memory": functools.wraps(get_memory_impl)(get_memory),
        "add_memory": functools.wraps(add_memory_impl)(add_memory),
        "move_to_location": functools.wraps(move_to_location_impl)(move_to_location),
    }

    return CHAT_TOOL_DEFINITIONS, callables


# Read-only tools available to the writing stage (no state mutations)
_WRITER_TOOL_NAMES = {"get_location_info", "get_npc_info", "search", "get_lore", "get_memory"}


def get_writer_tools(
    world_id: int, session_id: int,
) -> tuple[list[dict[str, Any]], dict[str, Callable]]:
    """Return read-only tools for the writing stage (no add_memory, move_to_location, web_search)."""
    all_defs, all_callables = get_chat_tools(world_id, session_id)

    writer_defs = [d for d in all_defs if d["function"]["name"] in _WRITER_TOOL_NAMES]
    writer_callables = {k: v for k, v in all_callables.items() if k in _WRITER_TOOL_NAMES}

    return writer_defs, writer_callables


def get_planning_tools(
    world_id: int,
    session_id: int,
    planning_context: "PlanningContext",
    stat_defs: list["WorldStatDefinition"],
    char_stats: dict[str, Any],
    world_stats: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Callable]]:
    """Return all 8 chat tools + 3 planning tools for the planning stage.

    Planning tool callables are closures that mutate planning_context and stats dicts.
    """
    from app.models.schemas.pipeline import PlanningContext, StatUpdateEntry
    from app.models.world import WorldStatDefinition
    from app.services.stat_validation import validate_and_apply_stat_updates

    chat_defs, chat_callables = get_chat_tools(world_id, session_id)

    # Planning tool closures
    async def add_fact_impl(content: str) -> str:
        planning_context.facts.append(content)
        return f"Fact recorded ({len(planning_context.facts)} total)."

    async def add_decision_impl(content: str) -> str:
        planning_context.decisions.append(content)
        return f"Decision recorded ({len(planning_context.decisions)} total)."

    async def update_stat_impl(name: str, value: str) -> str:
        updates = {name: value}
        try:
            new_char, new_world = validate_and_apply_stat_updates(
                updates, stat_defs, char_stats, world_stats,
            )
        except Exception as exc:
            return f"Stat update failed: {exc}"

        # Check if the stat was actually applied (validate silently skips invalid)
        if new_char == char_stats and new_world == world_stats:
            return f"Stat update rejected: '{name}' is not a valid stat or value '{value}' is invalid."

        # Apply mutations to the shared dicts
        char_stats.update(new_char)
        world_stats.update(new_world)
        planning_context.stat_updates.append(StatUpdateEntry(name=name, value=value))
        return f"Stat updated: {name} = {value}"

    planning_callables: dict[str, Callable] = {
        "add_fact": add_fact_impl,
        "add_decision": add_decision_impl,
        "update_stat": update_stat_impl,
    }

    all_defs = chat_defs + PLANNING_TOOL_DEFINITIONS
    all_callables = {**chat_callables, **planning_callables}

    return all_defs, all_callables
