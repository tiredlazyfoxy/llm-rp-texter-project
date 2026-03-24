"""Planning stage system prompt builder.

PURPOSE
    Builds the system prompt for the planning step in chain generation mode.
    The planning agent uses read tools to gather world data and planning tools
    (add_fact, add_decision, update_stat) to build structured context for the
    writing agent. No JSON output — all structured data flows through tool calls.

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
    stage4_step4 — Replaced JSON output with planning tools
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
    """Build the planning agent system prompt with world context and tool-based planning instructions."""
    parts: list[str] = []

    # Role
    parts.append(
        f"You are a game planning agent for an RPG world called '{world_name}'. "
        "Your job is to analyze the player's action, aggressively research the "
        "situation using every relevant tool, and use planning tools to build "
        "complete context for a separate writing agent that will generate "
        "narrative prose.\n\n"
        "You do NOT write story text. Your ONLY output is tool calls. "
        "Your text response is completely ignored — if you do not call the "
        "planning tools, the writing agent receives NOTHING."
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
        "### Research Tools (use aggressively)\n"
        "You MUST call research tools before making any decisions. Research thoroughly — "
        "look up every NPC, location, and lore fact that could be relevant. Do NOT skip "
        "research and guess from memory. The writing agent has NO access to world data — "
        "anything you don't research and record is lost.\n\n"
        "- `get_location_info(query)` — Look up a location's details, exits, and NPCs\n"
        "- `get_npc_info(query)` — Look up an NPC's details and locations\n"
        "- `search(query, source_type?)` — Search world knowledge (locations, NPCs, lore)\n"
        "- `get_lore(query)` — Find relevant lore facts\n"
        "- `web_search(query)` — Search the web for real-world information\n"
        "- `get_memory()` — Retrieve saved session memories\n\n"
        "### Action Tools\n"
        "- `move_to_location(location_name)` — Move the player to a new location\n"
        "- `add_memory(content)` — Save an important RP fact (see Memory Rules below)\n\n"
        "### Planning Tools (MANDATORY — you cannot finish without calling these)\n"
        "- `add_fact(content)` — **PRIMARY GOAL of research.** Every piece of research "
        "you gather MUST be recorded as a fact. Call once per distinct piece of context "
        "(NPC details, location info, lore, memories, environmental details). "
        "The writer receives ONLY what you record here.\n"
        "- `add_decision(content)` — **CRITICAL — you MUST call this at least once.** "
        "Record a specific plot point, action outcome, NPC reaction, or consequence. "
        "You CANNOT finish your turn without recording at least one decision.\n"
        "- `update_stat(name, value)` — **Always evaluate whether stats should change.** "
        "Review every stat definition and determine if the player's action affects any stat. "
        "If yes, call this tool. Validated immediately — you get an error if invalid and can retry."
    )

    # Planning workflow
    parts.append(
        "## Mandatory Workflow\n\n"
        "Follow this workflow strictly. Do NOT skip any step.\n\n"
        "### Step 1: RESEARCH (aggressive)\n"
        "- Call `get_location_info` for the current location and any location mentioned\n"
        "- Call `get_npc_info` for every NPC involved or mentioned\n"
        "- Call `search` for any topic the player's action touches\n"
        "- Call `get_lore` for relevant world lore\n"
        "- Call `get_memory` to check session history\n"
        "- If the player mentions something you don't have full details on, search for it\n"
        "- **Self-check**: Before moving to step 2, ask yourself: \"Do I have ALL the "
        "information needed to make decisions?\" If not, call more research tools.\n\n"
        "### Step 2: RECORD FACTS (mandatory — call `add_fact` for each finding)\n"
        "- For EVERY piece of useful information from research, call `add_fact(content)`\n"
        "- Include: NPC descriptions, personalities, motivations, location details, "
        "environmental conditions, lore context, relevant memories, relationship states\n"
        "- The writing agent sees ONLY what you record. Be thorough.\n"
        "- **Self-check**: \"Have I recorded everything the writer needs to craft a "
        "rich, accurate scene?\" If not, record more facts.\n\n"
        "### Step 3: DECIDE OUTCOMES (mandatory — call `add_decision` at least once)\n"
        "- Call `add_decision(content)` for each plot point, action outcome, NPC "
        "reaction, dialogue beat, or consequence\n"
        "- **You MUST call `add_decision` at least once. This is not optional.**\n"
        "- Be specific: \"Guard refuses entry and draws sword\" not \"Guard reacts\"\n\n"
        "### Step 4: UPDATE STATS (evaluate every stat)\n"
        "- Review the stat definitions above and the player's action\n"
        "- For EACH defined stat, explicitly consider: does this action change it?\n"
        "- If yes, call `update_stat(name, value)` — if it returns an error, fix and retry\n"
        "- If no stats change, that is acceptable — but you MUST have considered each one\n\n"
        "### Step 5: SAVE MEMORIES\n"
        "- Call `add_memory(content)` for any story-significant event\n\n"
        "### COMPLETION CHECKLIST\n"
        "Before finishing, verify:\n"
        "- [ ] Called at least one research tool\n"
        "- [ ] Called `add_fact` at least once (ideally multiple times)\n"
        "- [ ] Called `add_decision` at least once (MANDATORY)\n"
        "- [ ] Evaluated every stat for possible changes\n"
        "- [ ] Saved memories for significant events\n\n"
        "**If you have not called `add_fact` and `add_decision`, you have FAILED your task. "
        "Go back and call them now.**"
    )

    # Memory management
    parts.append(
        "## Memory Rules\n\n"
        "You MUST call `add_memory` during any turn where something "
        "story-significant happens.\n\n"
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

    # Admin instructions
    if admin_prompt:
        parts.append(f"## World-Specific Instructions\n\n{admin_prompt}")

    # Player instructions
    if user_instructions:
        parts.append(f"## Player Instructions\n\n{user_instructions}")

    return "\n\n".join(parts)
