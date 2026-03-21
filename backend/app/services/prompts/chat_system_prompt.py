"""Chat system prompt builder — rich context version.

PURPOSE
    Builds the full system prompt for chat generation (simple mode).
    Incorporates all world context: location, NPCs, rules, stats, lore, memories.

USAGE
    Called by simple_generation_service with context from build_chat_context().
    Chain mode's writing stage may also use this for world context.

VARIABLES
    world_name, world_description, admin_system_prompt, location_name,
    location_description, location_exits, present_npcs, rules,
    stat_definitions, current_stats, character_name, character_description,
    injected_lore, user_instructions, memories

DESIGN RATIONALE
    Sections ordered by decreasing structural importance:
    world context -> situation -> character -> instructions -> memories.
    Each section only included if non-empty to avoid blank blocks.

CHANGELOG
    stage2_step2 — Initial stub
    stage3_step2a — Full rich prompt implementation
"""


def build_rich_chat_system_prompt(
    world_name: str,
    world_description: str,
    admin_system_prompt: str,
    location_name: str,
    location_description: str,
    location_exits: str,
    present_npcs: str,
    rules: str,
    stat_definitions: str,
    current_stats: str,
    character_name: str,
    character_description: str,
    injected_lore: str,
    user_instructions: str,
    memories: str,
) -> str:
    """Build the full rich system prompt with all world context."""
    parts: list[str] = []

    # Core narrator intro
    parts.append(
        f"You are the narrator and game master for an RPG world called '{world_name}'. "
        "You control the world, NPCs, and story. Respond to the player's actions with "
        "immersive narrative prose. Stay in character as the narrator at all times."
    )

    # World
    if world_description:
        parts.append(f"## World\n\n{world_description}")

    # Current Location
    if location_name:
        loc_parts = [f"## Current Location\n\n**{location_name}**"]
        if location_description:
            loc_parts.append(location_description)
        if location_exits:
            loc_parts.append(f"**Exits:** {location_exits}")
        loc_parts.append(
            "When the player moves to a different location, you MUST call the "
            "`move_to_location` tool with the exact location name before describing "
            "the new location in your narrative."
        )
        parts.append("\n\n".join(loc_parts))

    # NPCs Present
    if present_npcs:
        parts.append(f"## NPCs Present\n\n{present_npcs}")

    # World Rules
    if rules:
        parts.append(f"## World Rules\n\n{rules}")

    # Stats
    if stat_definitions or current_stats:
        stat_parts = ["## Stats"]
        if stat_definitions:
            stat_parts.append("### Stat Definitions\n")
            stat_parts.append(stat_definitions)
        if current_stats:
            stat_parts.append("### Current Values\n")
            stat_parts.append(current_stats)
        stat_parts.append(
            "### Updating Stats\n"
            "When game events change stats, include a stat update block at the end "
            "of your response in this exact format:\n\n"
            "[STAT_UPDATE]\n"
            '{"stat_name": new_value, "another_stat": new_value}\n'
            "[/STAT_UPDATE]\n\n"
            "Only include stats that actually changed. Values must match the stat type "
            "(integer for int stats, string for enum stats, list of strings for set stats)."
        )
        parts.append("\n\n".join(stat_parts))

    # World Context (injected lore)
    if injected_lore:
        parts.append(f"## World Context\n\n{injected_lore}")

    # Character
    if character_name:
        char_text = f"## Your Character\n\n**{character_name}**"
        if character_description:
            char_text += f"\n\n{character_description}"
        parts.append(char_text)

    # Game Master Instructions (admin prompt)
    if admin_system_prompt:
        parts.append(f"## Game Master Instructions\n\n{admin_system_prompt}")

    # Player Instructions
    if user_instructions:
        parts.append(f"## Player Instructions\n\n{user_instructions}")

    # Memories
    if memories:
        parts.append(f"## Memories\n\n{memories}")

    return "\n\n".join(parts)


def build_chat_system_prompt(
    world_name: str,
    world_description: str,
    world_lore: str,
    character_name: str,
    character_description: str,
    user_instructions: str,
) -> str:
    """Deprecated wrapper — use build_rich_chat_system_prompt() instead."""
    return build_rich_chat_system_prompt(
        world_name=world_name,
        world_description=world_description,
        admin_system_prompt="",
        location_name="",
        location_description="",
        location_exits="",
        present_npcs="",
        rules="",
        stat_definitions="",
        current_stats="",
        character_name=character_name,
        character_description=character_description,
        injected_lore=world_lore,
        user_instructions=user_instructions,
        memories="",
    )
