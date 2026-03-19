"""Admin LLM tools — search, get_lore, web_search.

PURPOSE
-------
Defines the three MCP-style tools available to admin/editor users during
LLM-assisted world document editing. These are NOT available to player chat.

TOOLS
-----
- search(query, source_type?)  — semantic search across world knowledge chunks,
  returns full text of top-5 matching documents combined with a delimiter.
- get_lore(query)              — semantic search scoped to lore_fact only,
  returns single most relevant lore document.
- web_search(query)            — Google Custom Search, returns formatted results.

USAGE
-----
- Import ADMIN_TOOL_DEFINITIONS for the OpenAI tool schema list.
- Call get_admin_tools(world_id) to get {name: async_callable} dict bound to a world.
- Callables are passed directly to client.chat_with_tools().

ENV VARS (web_search)
---------------------
- SEARCH_CSE_KEY  — Google Custom Search API key
- SEARCH_CSE_ID   — Google Custom Search Engine ID
"""

import logging
import os
from collections.abc import Callable
from typing import Any

import aiohttp
from pydantic import BaseModel

from llm import pydantic_to_openai_tool

logger = logging.getLogger(__name__)

_GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
_DOCUMENT_DELIMITER = "\n\n---\n\n"


# ---------------------------------------------------------------------------
# Parameter schemas (used by pydantic_to_openai_tool)
# ---------------------------------------------------------------------------

class SearchParams(BaseModel):
    query: str
    source_type: str | None = None  # "location" | "npc" | "lore_fact" | None


class GetLoreParams(BaseModel):
    query: str


class WebSearchParams(BaseModel):
    query: str


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling format)
# ---------------------------------------------------------------------------

ADMIN_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    pydantic_to_openai_tool(
        "search",
        (
            "Search world knowledge by semantic similarity. "
            "Returns full text of the top matching documents (locations, NPCs, or lore facts). "
            "Use source_type to restrict to a specific document type: "
            "'location', 'npc', or 'lore_fact'. Omit source_type to search all types."
        ),
        SearchParams,
    ),
    pydantic_to_openai_tool(
        "get_lore",
        (
            "Find the most relevant lore fact for a query. "
            "Returns the full text of the single best matching lore entry. "
            "Use this when you need specific world lore or background information."
        ),
        GetLoreParams,
    ),
    pydantic_to_openai_tool(
        "web_search",
        (
            "Search the web using Google. "
            "Returns titles, URLs, and snippets for the top results. "
            "Use this for real-world information not present in the world documents."
        ),
        WebSearchParams,
    ),
]


# ---------------------------------------------------------------------------
# Pure async implementations
# ---------------------------------------------------------------------------

async def search_impl(
    world_id: int,
    query: str,
    source_type: str | None = None,
) -> str:
    """Vector search → fetch full documents → combine with delimiter."""
    from app.db import lore_facts, locations, npcs
    from app.services import vector_storage

    chunks = await vector_storage.search(world_id, query, source_type=source_type, limit=5)
    if not chunks:
        return "No results found."

    # Deduplicate by source_id, preserving relevance order
    seen: set[int] = set()
    unique: list[tuple[str, int]] = []
    for chunk in chunks:
        if chunk.source_id not in seen:
            seen.add(chunk.source_id)
            unique.append((chunk.source_type, chunk.source_id))

    parts: list[str] = []
    for src_type, src_id in unique:
        if src_type == "location":
            doc = await locations.get_by_id(src_id)
            if doc:
                parts.append(f"**Location: {doc.name}**\n\n{doc.content}")
        elif src_type == "npc":
            doc = await npcs.get_by_id(src_id)
            if doc:
                parts.append(f"**NPC: {doc.name}**\n\n{doc.content}")
        elif src_type == "lore_fact":
            doc = await lore_facts.get_by_id(src_id)
            if doc and doc.content:
                parts.append(f"**Lore Fact**\n\n{doc.content}")

    if not parts:
        return "No results found."

    logger.debug("search_impl: returned %d documents for world %d", len(parts), world_id)
    return _DOCUMENT_DELIMITER.join(parts)


async def get_lore_impl(world_id: int, query: str) -> str:
    """Vector search scoped to lore_fact, returns single full document."""
    from app.db import lore_facts
    from app.services import vector_storage

    chunks = await vector_storage.search(world_id, query, source_type="lore_fact", limit=1)
    if not chunks:
        return "No lore found."

    doc = await lore_facts.get_by_id(chunks[0].source_id)
    if doc is None or not doc.content:
        return "No lore found."

    logger.debug("get_lore_impl: found lore fact %d for world %d", doc.id, world_id)
    return doc.content


async def web_search_impl(query: str) -> str:
    """Google Custom Search — returns formatted title/URL/snippet list."""
    api_key = os.environ.get("SEARCH_CSE_KEY")
    cse_id = os.environ.get("SEARCH_CSE_ID")

    if not api_key or not cse_id:
        return (
            "Web search is not configured. "
            "Set SEARCH_CSE_KEY and SEARCH_CSE_ID environment variables."
        )

    params = {"key": api_key, "cx": cse_id, "q": query, "num": 5}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(_GOOGLE_CSE_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                resp.raise_for_status()
                data = await resp.json()
    except Exception as exc:
        logger.warning("web_search_impl failed: %s", exc)
        return f"Web search failed: {exc}"

    items = data.get("items", [])
    if not items:
        return "No web results found."

    lines: list[str] = []
    for i, item in enumerate(items, 1):
        title = item.get("title", "")
        link = item.get("link", "")
        snippet = item.get("snippet", "").replace("\n", " ")
        lines.append(f"{i}. {title}\n{link}\n{snippet}")

    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_admin_tools(world_id: int) -> dict[str, Callable]:
    """Return {tool_name: async_callable} bound to the given world_id."""
    return {
        "search": lambda query, source_type=None: search_impl(world_id, query, source_type),
        "get_lore": lambda query: get_lore_impl(world_id, query),
        "web_search": web_search_impl,
    }
