"""Tool Catalog.

Derived view over the single tool registry in
:mod:`app.services.chat_tools`. Used by:

- Admin UI: tool selection checkboxes/chips
- ``{TOOLS}`` placeholder resolution
- Validation of ``PipelineStage.tools`` and ``World.simple_tools``

The registry (``TOOL_REGISTRY``) is the source of truth for tool name,
description, and category. This module only reshapes it into the
typed list the admin API returns.
"""

from typing import TypedDict

from app.services.chat_tools import TOOL_REGISTRY


class ToolCatalogEntry(TypedDict):
    name: str
    description: str
    category: str  # "research", "action", "planning", "director"


TOOL_CATALOG: list[ToolCatalogEntry] = [
    {
        "name": spec.name,
        "description": spec.description,
        "category": spec.category,
    }
    for spec in TOOL_REGISTRY.values()
]

ALL_TOOL_NAMES: set[str] = set(TOOL_REGISTRY.keys())
