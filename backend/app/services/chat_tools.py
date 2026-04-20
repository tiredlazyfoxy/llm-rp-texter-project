"""Chat tools — universal tool registry for all generation modes.

PURPOSE
    Single source of truth for every tool the LLM may call during chat
    generation. One registry declares each tool's parameter schema,
    description, category, and required runtime state. One factory —
    ``build_tools(names, ctx)`` — returns exactly the tools the caller
    asked for, binding them to the state present in ``ToolContext``.
    There are no per-stage tool bundles in code: the admin pipeline
    editor picks the names for every stage (tool / writer / simple /
    director), and the caller supplies whatever state it has.

USAGE
    ctx = ToolContext(world_id=..., session_id=..., planning_context=...,
                      decision_state=..., stat_defs=..., char_stats=...,
                      world_stats=...)
    tool_defs, callables = build_tools(stage.tools, ctx)

    Unknown name           → ValueError.
    Tool requires state    → ValueError listing the missing keys.

CHANGELOG
    stage3_step2a — Created (8 chat + 3 planning tools, per-stage factories).
    stage5_step3  — Added set_decision director tool + DecisionState.
    stage5_step4  — Unified into a single ToolContext + build_tools factory;
                    dropped CHAT/PLANNING/DIRECTOR/WRITER tool group constants
                    and per-stage factories.
"""

from __future__ import annotations

import functools
import json
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from llm import pydantic_to_openai_tool

from app.services import admin_tools

if TYPE_CHECKING:
    from app.models.schemas.pipeline import PlanningContext
    from app.models.world import WorldStatDefinition

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


class AddFactParams(BaseModel):
    content: str


class AddDecisionParams(BaseModel):
    content: str


class UpdateStatParams(BaseModel):
    name: str
    value: str


class SetDecisionParams(BaseModel):
    content: str


class DecisionState:
    """Mutable holder for the director's single-decision output."""

    def __init__(self) -> None:
        self.decision: str = ""


# ---------------------------------------------------------------------------
# Tool implementations (pure, state-free except for the explicit args)
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

    seen: set[int] = set()
    for chunk in chunks:
        if chunk.source_id in seen:
            continue
        seen.add(chunk.source_id)

        location = await locations_db.get_by_id(chunk.source_id)
        if not location:
            continue

        parts = [f"**Location: {location.name}**\n\n{location.content}"]

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
    """Resolve location name → ID, update session, return new location info as JSON."""
    from app.db import chats as chats_db
    from app.db import locations as locations_db
    from app.db import npc_links as npc_links_db
    from app.db import npcs as npcs_db
    from app.services import vector_storage

    location = None
    chunks = await vector_storage.search(world_id, location_name, source_type="location", limit=1)
    if chunks:
        location = await locations_db.get_by_id(chunks[0].source_id)

    if location is None:
        return json.dumps({"status": "ERROR", "reason": f"Location '{location_name}' not found in this world."})

    chat = await chats_db.get_session_by_id(session_id)
    if chat is None:
        return json.dumps({"status": "ERROR", "reason": "Session not found."})

    # Build location info (reused for both OK and REJECTED)
    exit_names: list[str] = []
    if location.exits:
        try:
            exit_ids = json.loads(location.exits)
            for eid in exit_ids:
                loc = await locations_db.get_by_id(int(eid))
                if loc:
                    exit_names.append(loc.name)
        except (json.JSONDecodeError, ValueError):
            pass

    npcs_list: list[dict[str, str]] = []
    links = await npc_links_db.list_by_location(location.id)
    present_npcs = [lnk for lnk in links if lnk.link_type.value == "present"]
    for link in present_npcs:
        npc = await npcs_db.get_by_id(link.npc_id)
        if npc:
            brief = npc.content.split("\n\n")[0] if npc.content else ""
            npcs_list.append({"name": npc.name, "brief": brief})

    location_info = {
        "name": location.name,
        "description": location.content or "",
        "exits": exit_names,
        "npcs": npcs_list,
    }

    # Check if already at this location
    if chat.current_location_id == location.id:
        logger.info("Player already at '%s' (id=%d) in session %d", location.name, location.id, session_id)
        return json.dumps({"status": "REJECTED", "reason": f"Player is already at '{location.name}'. No move needed.", "location": location_info})

    chat.current_location_id = location.id
    chat.modified_at = datetime.now(timezone.utc)
    await chats_db.update_session(chat)

    logger.info("Player moved to '%s' (id=%d) in session %d", location.name, location.id, session_id)
    return json.dumps({"status": "OK", "location": location_info})


async def _get_injected_ids(world_id: int) -> set[int]:
    """Return IDs of lore facts always injected into context."""
    from app.db import lore_facts
    facts = await lore_facts.list_injected_by_world(world_id)
    return {f.id for f in facts}


# ---------------------------------------------------------------------------
# ToolContext — the bundle of runtime state carried by callers
# ---------------------------------------------------------------------------

@dataclass
class ToolContext:
    """Runtime state available to a generation step.

    Callers populate whichever fields they have. The registry's ``requires``
    list decides whether a tool can be instantiated from this context.
    """

    world_id: int | None = None
    session_id: int | None = None
    planning_context: "PlanningContext | None" = None
    stat_defs: "list[WorldStatDefinition] | None" = None
    char_stats: dict[str, Any] | None = None
    world_stats: dict[str, Any] | None = None
    decision_state: DecisionState | None = None

    def has(self, key: str) -> bool:
        return getattr(self, key) is not None


# ---------------------------------------------------------------------------
# Builders — per tool, a closure factory that binds ctx fields
# ---------------------------------------------------------------------------

def _b_get_location_info(ctx: ToolContext) -> Callable:
    assert ctx.world_id is not None
    world_id = ctx.world_id
    async def get_location_info(query: str) -> str:
        return await get_location_info_impl(world_id, query)
    return functools.wraps(get_location_info_impl)(get_location_info)


def _b_get_npc_info(ctx: ToolContext) -> Callable:
    assert ctx.world_id is not None
    world_id = ctx.world_id
    async def get_npc_info(query: str) -> str:
        return await get_npc_info_impl(world_id, query)
    return functools.wraps(get_npc_info_impl)(get_npc_info)


def _b_search(ctx: ToolContext) -> Callable:
    assert ctx.world_id is not None
    world_id = ctx.world_id
    async def search(query: str, source_type: str | None = None) -> str:
        injected_ids = await _get_injected_ids(world_id)
        return await admin_tools.search_impl(world_id, query, source_type, injected_ids)
    return functools.wraps(admin_tools.search_impl)(search)


def _b_get_lore(ctx: ToolContext) -> Callable:
    assert ctx.world_id is not None
    world_id = ctx.world_id
    async def get_lore(query: str) -> str:
        injected_ids = await _get_injected_ids(world_id)
        return await admin_tools.get_lore_impl(world_id, query, injected_ids)
    return functools.wraps(admin_tools.get_lore_impl)(get_lore)


def _b_web_search(_ctx: ToolContext) -> Callable:
    async def web_search(query: str) -> str:
        return await admin_tools.web_search_impl(query)
    return functools.wraps(admin_tools.web_search_impl)(web_search)


def _b_get_memory(ctx: ToolContext) -> Callable:
    assert ctx.session_id is not None
    session_id = ctx.session_id
    async def get_memory() -> str:
        return await get_memory_impl(session_id)
    return functools.wraps(get_memory_impl)(get_memory)


def _b_add_memory(ctx: ToolContext) -> Callable:
    assert ctx.session_id is not None
    session_id = ctx.session_id
    async def add_memory(content: str) -> str:
        return await add_memory_impl(session_id, content)
    return functools.wraps(add_memory_impl)(add_memory)


def _b_move_to_location(ctx: ToolContext) -> Callable:
    assert ctx.world_id is not None and ctx.session_id is not None
    world_id = ctx.world_id
    session_id = ctx.session_id
    async def move_to_location(location_name: str) -> str:
        return await move_to_location_impl(world_id, session_id, location_name)
    return functools.wraps(move_to_location_impl)(move_to_location)


def _b_add_fact(ctx: ToolContext) -> Callable:
    assert ctx.planning_context is not None
    pc = ctx.planning_context
    async def add_fact(content: str) -> str:
        pc.facts.append(content)
        return f"Fact recorded ({len(pc.facts)} total)."
    return add_fact


def _b_add_decision(ctx: ToolContext) -> Callable:
    assert ctx.planning_context is not None
    pc = ctx.planning_context
    async def add_decision(content: str) -> str:
        pc.decisions.append(content)
        return f"Decision recorded ({len(pc.decisions)} total)."
    return add_decision


def _b_update_stat(ctx: ToolContext) -> Callable:
    from app.models.schemas.pipeline import StatUpdateEntry
    from app.services.stat_validation import validate_single_value

    assert (
        ctx.planning_context is not None
        and ctx.stat_defs is not None
        and ctx.char_stats is not None
        and ctx.world_stats is not None
    )
    pc = ctx.planning_context
    stat_defs = ctx.stat_defs
    char_stats = ctx.char_stats
    world_stats = ctx.world_stats

    defs_by_name = {d.name: d for d in stat_defs}

    def _all_stats() -> dict[str, str]:
        merged: dict[str, str] = {}
        merged.update({k: str(v) for k, v in char_stats.items()})
        merged.update({k: str(v) for k, v in world_stats.items()})
        return merged

    async def update_stat(name: str, value: str) -> str:
        # Phase 1: check stat name exists
        stat_def = defs_by_name.get(name)
        if stat_def is None:
            valid_names = sorted(defs_by_name.keys())
            return json.dumps({
                "status": "ERROR",
                "reason": f"Stat '{name}' is not recognized. Valid stats: {', '.join(valid_names)}",
                "all_stats": _all_stats(),
            })

        # Phase 2: validate value
        validated = validate_single_value(stat_def, value)
        if validated is None:
            stat_type = stat_def.stat_type.value
            if stat_type == "int":
                hint = "Expected integer"
                if stat_def.min_value is not None or stat_def.max_value is not None:
                    hint += f" in range [{stat_def.min_value}, {stat_def.max_value}]"
            elif stat_type == "enum":
                hint = f"Expected one of: {stat_def.enum_values}"
            elif stat_type == "set":
                hint = f"Expected list from: {stat_def.enum_values}"
            else:
                hint = f"Unknown stat type '{stat_type}'"
            return json.dumps({
                "status": "ERROR",
                "reason": f"Value '{value}' is invalid for '{name}' ({stat_type}). {hint}",
                "all_stats": _all_stats(),
            })

        # Phase 3: check if value is already set
        target = char_stats if stat_def.scope.value == "character" else world_stats
        old_value = target.get(name)
        if old_value is not None and str(old_value) == str(validated):
            return json.dumps({
                "status": "REJECTED",
                "reason": f"Stat '{name}' already has value '{validated}'. No change needed.",
                "all_stats": _all_stats(),
            })

        # Phase 4: apply
        target[name] = validated
        pc.stat_updates.append(StatUpdateEntry(name=name, value=str(validated)))
        return json.dumps({
            "status": "OK",
            "updated_stat": {"name": name, "old_value": str(old_value) if old_value is not None else None, "new_value": str(validated)},
            "all_stats": _all_stats(),
        })

    return update_stat


def _b_set_decision(ctx: ToolContext) -> Callable:
    assert ctx.decision_state is not None
    state = ctx.decision_state
    async def set_decision(content: str) -> str:
        state.decision = content
        return "Decision committed."
    return set_decision


# ---------------------------------------------------------------------------
# Registry — single source of truth
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    category: str  # research | action | planning | director
    params: type[BaseModel]
    requires: tuple[str, ...]  # ToolContext field names that must be set
    build: Callable[[ToolContext], Callable]
    definition: dict[str, Any] = field(init=False, compare=False, hash=False, default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "definition",
            pydantic_to_openai_tool(self.name, self.description, self.params),
        )


TOOL_REGISTRY: dict[str, ToolSpec] = {
    spec.name: spec for spec in [
        ToolSpec(
            name="get_location_info",
            description=(
                "Look up detailed information about a location in the world. "
                "Returns the full location description, exits, and NPCs present there."
            ),
            category="research",
            params=GetLocationInfoParams,
            requires=("world_id",),
            build=_b_get_location_info,
        ),
        ToolSpec(
            name="get_npc_info",
            description=(
                "Look up detailed information about an NPC in the world. "
                "Returns the full NPC description and their known locations."
            ),
            category="research",
            params=GetNpcInfoParams,
            requires=("world_id",),
            build=_b_get_npc_info,
        ),
        ToolSpec(
            name="search",
            description=(
                "Search world knowledge by semantic similarity. "
                "Returns matching documents (locations, NPCs, or lore facts). "
                "Use source_type to filter: 'location', 'npc', or 'lore_fact'."
            ),
            category="research",
            params=SearchParams,
            requires=("world_id",),
            build=_b_search,
        ),
        ToolSpec(
            name="get_lore",
            description=(
                "Find the most relevant lore fact for a query. "
                "Returns the full text of the best matching lore entry."
            ),
            category="research",
            params=GetLoreParams,
            requires=("world_id",),
            build=_b_get_lore,
        ),
        ToolSpec(
            name="web_search",
            description=(
                "Search the web for real-world information not in the world documents. "
                "Returns titles, URLs, and snippets."
            ),
            category="research",
            params=WebSearchParams,
            requires=(),
            build=_b_web_search,
        ),
        ToolSpec(
            name="get_memory",
            description="Retrieve all saved memories for this session.",
            category="research",
            params=GetMemoryParams,
            requires=("session_id",),
            build=_b_get_memory,
        ),
        ToolSpec(
            name="add_memory",
            description=(
                "Save an important fact or observation to session memory "
                "for future reference."
            ),
            category="action",
            params=AddMemoryParams,
            requires=("session_id",),
            build=_b_add_memory,
        ),
        ToolSpec(
            name="move_to_location",
            description=(
                "Move the player to a different location. Use the exact location name "
                "as shown in exits or search results. Returns JSON with status "
                "(OK/REJECTED/ERROR) and location details (description, exits, NPCs). "
                "REJECTED means the player is already there — do not retry."
            ),
            category="action",
            params=MoveToLocationParams,
            requires=("world_id", "session_id"),
            build=_b_move_to_location,
        ),
        ToolSpec(
            name="add_fact",
            description=(
                "Record a relevant observation or piece of context that the writing "
                "agent needs to craft the narrative. Call once per distinct fact."
            ),
            category="planning",
            params=AddFactParams,
            requires=("planning_context",),
            build=_b_add_fact,
        ),
        ToolSpec(
            name="add_decision",
            description=(
                "Record a specific plot point, action outcome, or NPC reaction "
                "for this turn. The writing agent will follow these faithfully."
            ),
            category="planning",
            params=AddDecisionParams,
            requires=("planning_context",),
            build=_b_add_decision,
        ),
        ToolSpec(
            name="update_stat",
            description=(
                "Update a stat value. Returns JSON with status (OK/REJECTED/ERROR), "
                "the updated stat details, and a snapshot of all current stat values. "
                "REJECTED means the stat already has that value — do not retry."
            ),
            category="planning",
            params=UpdateStatParams,
            requires=("planning_context", "stat_defs", "char_stats", "world_stats"),
            build=_b_update_stat,
        ),
        ToolSpec(
            name="set_decision",
            description=(
                "Commit the single short decision (one sentence) describing what "
                "will happen next turn. Overwrites any previous decision. "
                "Do not plan details — just the top-level narrative direction."
            ),
            category="director",
            params=SetDecisionParams,
            requires=("decision_state",),
            build=_b_set_decision,
        ),
    ]
}


ALL_TOOL_NAMES: tuple[str, ...] = tuple(TOOL_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def build_tools(
    tool_names: Iterable[str],
    ctx: ToolContext,
) -> tuple[list[dict[str, Any]], dict[str, Callable]]:
    """Instantiate the named tools against the given context.

    - Unknown tool name → ``ValueError``.
    - Tool with unmet ``requires`` → ``ValueError`` listing missing fields.
    - Order of returned definitions mirrors the order of ``tool_names``.
    """
    defs: list[dict[str, Any]] = []
    callables: dict[str, Callable] = {}
    seen: set[str] = set()

    for name in tool_names:
        if name in seen:
            continue
        seen.add(name)

        spec = TOOL_REGISTRY.get(name)
        if spec is None:
            raise ValueError(f"Unknown tool '{name}'.")

        missing = [req for req in spec.requires if not ctx.has(req)]
        if missing:
            raise ValueError(
                f"Tool '{name}' requires context fields {missing} which are not set."
            )

        defs.append(spec.definition)
        callables[name] = spec.build(ctx)

    return defs, callables
