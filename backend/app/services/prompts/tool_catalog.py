"""Tool Catalog.

Static registry of all available tools that can be assigned to pipeline stages
or simple mode. Used by:

- Admin UI: tool selection checkboxes/chips
- ``{TOOLS}`` placeholder resolution (Step 2)
- Validation of ``PipelineStage.tools`` and ``World.simple_tools``
"""

from typing import TypedDict


class ToolCatalogEntry(TypedDict):
    name: str
    description: str
    category: str  # "research", "action", "planning"


TOOL_CATALOG: list[ToolCatalogEntry] = [
    # Research
    {"name": "get_location_info", "description": "Look up location details, exits, and NPCs present", "category": "research"},
    {"name": "get_npc_info", "description": "Look up NPC details and their locations", "category": "research"},
    {"name": "search", "description": "Semantic search across world knowledge (locations, NPCs, lore)", "category": "research"},
    {"name": "get_lore", "description": "Find the most relevant lore fact for a query", "category": "research"},
    {"name": "web_search", "description": "Search the web for real-world information", "category": "research"},
    {"name": "get_memory", "description": "Retrieve all saved session memories", "category": "research"},
    # Action
    {"name": "add_memory", "description": "Save an important fact to session memory", "category": "action"},
    {"name": "move_to_location", "description": "Move the player to a different location", "category": "action"},
    # Planning (chain mode tool steps)
    {"name": "add_fact", "description": "Record a context fact for the writing agent", "category": "planning"},
    {"name": "add_decision", "description": "Record a narrative decision for the writing agent", "category": "planning"},
    {"name": "update_stat", "description": "Update a stat value (validated immediately)", "category": "planning"},
]

ALL_TOOL_NAMES: set[str] = {t["name"] for t in TOOL_CATALOG}
