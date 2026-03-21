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
    stage3_step2b — Full prompt implementation
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
    """Build the planning agent system prompt with world context and JSON schema."""
    parts: list[str] = []

    # Role
    parts.append(
        f"You are a game planning agent for an RPG world called '{world_name}'. "
        "Your job is to analyze the player's action, gather relevant information "
        "using the available tools, and produce a structured JSON plan that a "
        "separate writing agent will use to generate narrative prose.\n\n"
        "You do NOT write story text. You only produce a JSON planning document."
    )

    # World context
    if world_description:
        parts.append(f"## World\n\n{world_description}")

    if location_name:
        loc_parts = [f"## Current Location\n\n**{location_name}**"]
        if location_description:
            loc_parts.append(location_description)
        if location_exits:
            loc_parts.append(f"**Exits:** {location_exits}")
        loc_parts.append(
            "When the player moves to a different location, you MUST call the "
            "`move_to_location` tool with the exact location name."
        )
        parts.append("\n\n".join(loc_parts))

    if present_npcs:
        parts.append(f"## NPCs Present\n\n{present_npcs}")

    if rules:
        parts.append(f"## World Rules\n\n{rules}")

    if stat_definitions or current_stats:
        stat_parts = ["## Stats"]
        if stat_definitions:
            stat_parts.append("### Stat Definitions\n")
            stat_parts.append(stat_definitions)
        if current_stats:
            stat_parts.append("### Current Values\n")
            stat_parts.append(current_stats)
        parts.append("\n\n".join(stat_parts))

    if lore_parts:
        parts.append(f"## World Context\n\n{lore_parts}")

    if character_name:
        char_text = f"## Player Character\n\n**{character_name}**"
        if character_description:
            char_text += f"\n\n{character_description}"
        parts.append(char_text)

    # Tool instructions
    parts.append(
        "## Available Tools\n\n"
        "Use these tools to gather information before making your plan:\n"
        "- `get_location_info(query)` — Look up a location's details, exits, and NPCs\n"
        "- `get_npc_info(query)` — Look up an NPC's details and locations\n"
        "- `search(query, source_type?)` — Search world knowledge (locations, NPCs, lore)\n"
        "- `get_lore(query)` — Find relevant lore facts\n"
        "- `web_search(query)` — Search the web for real-world information\n"
        "- `get_memory()` — Retrieve saved session memories\n"
        "- `add_memory(content)` — Save an important RP fact (see Memory Rules below)\n"
        "- `move_to_location(location_name)` — Move the player to a new location\n\n"
        "Call tools as needed to understand the situation before planning your response. "
        "You do not need to call every tool — only the ones relevant to the player's action."
    )

    # Memory management
    parts.append(
        "## Memory Rules\n\n"
        "You MUST call `add_memory` after planning any turn where something "
        "story-significant happens. Save memories AFTER you have decided what happens, "
        "just before outputting the JSON plan.\n\n"
        "**What to save:**\n"
        "- Promises, deals, or commitments (player or NPC)\n"
        "- NPC relationship changes (trust, hostility, alliance)\n"
        "- Plot developments, secrets revealed, quests accepted/completed\n"
        "- Lasting consequences of player choices\n"
        "- Items acquired, lost, or traded\n\n"
        "**How to write memories:**\n"
        "- 1-2 short sentences per memory — fact, not prose\n"
        "- State what happened: \"Traded silver ring to Mira for river passage\"\n"
        "- State relationship shifts: \"Captain Voss now suspects player of theft\"\n\n"
        "**Do NOT save:** routine actions, location descriptions, combat details, "
        "or anything already tracked by stats or location."
    )

    # JSON output schema
    parts.append(
        '## Output Format\n\n'
        'After gathering information, output a single JSON object with this exact structure:\n\n'
        '```json\n'
        '{\n'
        '  "collected_data": "A summary of relevant context you gathered from tools and world state. '
        'Include NPC details, location info, lore facts, and any other relevant information '
        'the writer needs to craft the narrative.",\n'
        '  "stat_updates": [\n'
        '    {"name": "stat_name", "value": "new_value"}\n'
        '  ],\n'
        '  "decisions": [\n'
        '    "What happens in the scene — a specific plot point or action outcome",\n'
        '    "NPC dialogue or reaction to include",\n'
        '    "Environmental detail or consequence"\n'
        '  ]\n'
        '}\n'
        '```\n\n'
        '**Field descriptions:**\n'
        '- `collected_data`: Summarize ALL context the writer needs. The writer cannot call tools.\n'
        '- `stat_updates`: Only include stats that actually change. Use stat names exactly as defined. '
        'Values must match the stat type (integer for int stats, string for enum, list for set).\n'
        '- `decisions`: Specific, actionable plot points. The writer will follow these faithfully. '
        'Include NPC dialogue, action outcomes, discoveries, and consequences.\n\n'
        '**IMPORTANT:** Output ONLY the JSON object. No markdown fences, no commentary, '
        'no narrative prose. Just the raw JSON.'
    )

    # Admin instructions
    if admin_prompt:
        parts.append(f"## World-Specific Instructions\n\n{admin_prompt}")

    # Player instructions
    if user_instructions:
        parts.append(f"## Player Instructions\n\n{user_instructions}")

    return "\n\n".join(parts)
