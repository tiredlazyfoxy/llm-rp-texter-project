"""Planning stage system prompt builder.

PURPOSE
    Builds the system prompt for the planning step in chain generation mode.
    The planning agent uses tools to gather world data and produces structured
    JSON output (collected_data, decisions, stat_updates).

USAGE
    Called by chain_generation_service before the planning LLM call.

VARIABLES
    world_name          — Display name of the world
    world_description   — World description text
    location_name       — Current location name
    location_description — Current location content/description
    location_exits      — Formatted exit info for current location
    present_npcs        — NPCs present at current location
    rules               — Formatted world rules
    stat_definitions    — Stat schema definitions (names, types, ranges)
    current_stats       — Current stat values for the session
    character_name      — Player character name
    character_description — Player character description
    user_instructions   — Player-set instructions for the LLM
    lore_parts          — Injected lore facts
    admin_prompt        — Admin-editable free text (PipelineStage.prompt)

DESIGN RATIONALE
    Separated from writing prompt to allow independent iteration.
    The planning stage focuses on data gathering and decision-making,
    while the writing stage focuses on prose quality.

CHANGELOG
    stage3_step1 — Skeleton created (returns empty string)
"""


def build_planning_system_prompt(
    world_name: str,
    world_description: str,
    location_name: str,
    location_description: str,
    location_exits: str,
    present_npcs: str,
    rules: str,
    stat_definitions: str,
    current_stats: str,
    character_name: str,
    character_description: str,
    user_instructions: str,
    lore_parts: str,
    admin_prompt: str,
) -> str:
    """Placeholder — returns empty string until step 2."""
    return ""
