"""Placeholder Registry.

Static registry of all available prompt placeholders. Each placeholder is an
injection point — the code builds the formatted text, the admin just specifies
WHERE to inject it in the prompt via ``{PLACEHOLDER_NAME}`` syntax.

Used by:
- Backend prompt injection service (resolves values at runtime) — Step 2
- API: exposed via ``GET /api/admin/worlds/pipeline-config`` for frontend reference
- Admin LLM editor system prompt: documents available placeholders
"""

from typing import TypedDict


class PlaceholderInfo(TypedDict):
    name: str           # e.g. "WORLD_NAME"
    description: str    # human-readable for admin UI
    category: str       # "World", "Location", "Character", "Stats", "Context", "Pipeline"


PLACEHOLDER_REGISTRY: list[PlaceholderInfo] = [
    # World
    {"name": "WORLD_NAME", "description": "World display name", "category": "World"},
    {"name": "RULES", "description": "Numbered world rules list", "category": "World"},
    {"name": "INJECTED_LORE", "description": "Always-injected lore facts (sorted by weight)", "category": "World"},
    # Location
    {"name": "LOCATION", "description": "Full current location block: name, description, exits, and NPCs present. Code-formatted from session's current_location_id.", "category": "Location"},
    # Character
    {"name": "CHARACTER_NAME", "description": "Player character name", "category": "Character"},
    # Stats
    {"name": "CHARACTER_STATS", "description": "Character-scope stats: definitions and current values, code-formatted.", "category": "Stats"},
    {"name": "WORLD_STATS", "description": "World-scope stats: definitions and current values, code-formatted.", "category": "Stats"},
    # Context
    {"name": "USER_INSTRUCTIONS", "description": "Player-set custom instructions", "category": "Context"},
    # Pipeline
    {"name": "TURN_FACTS", "description": "Collected context/facts from previous tool steps. Only meaningful for writer step in chain mode.", "category": "Pipeline"},
    {"name": "TURN_DECISIONS", "description": "Decisions/outcomes to execute from previous tool steps. Only meaningful for writer step in chain mode.", "category": "Pipeline"},
    {"name": "DECISION", "description": "Short single-sentence decision committed by the director stage via set_decision. Empty string if no director stage ran.", "category": "Pipeline"},
    {"name": "TOOLS", "description": "Auto-generated list of available tools for this step with descriptions.", "category": "Pipeline"},
]

VALID_PLACEHOLDERS: set[str] = {p["name"] for p in PLACEHOLDER_REGISTRY}
