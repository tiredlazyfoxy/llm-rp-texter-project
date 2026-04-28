"""Writing stage system prompt builder.

PURPOSE
    Builds the system prompt for the writing step in chain generation mode.
    The writing LLM produces narrative prose based on the planning stage output.

USAGE
    Called by chain_generation_service before the writing LLM call.

VARIABLES
    world_name          — Display name of the world
    world_description   — World description text
    character_name      — Player character name
    character_description — Player character description
    lore_parts          — Injected lore facts
    admin_prompt        — Admin-editable free text (PipelineStage.prompt)
    user_instructions   — Player-set instructions for the LLM

DESIGN RATIONALE
    Receives minimal context — most world data was already processed by the
    planning stage. Focuses on tone, style, and narrative quality.

CHANGELOG
    stage3_step1 — Skeleton created (returns empty string)
    stage3_step2b — Full prompt implementation
"""


def build_writing_system_prompt(
    world_name: str,
    world_description: str,
    character_name: str,
    character_description: str,
    lore_parts: str,
    admin_prompt: str,
    user_instructions: str = "",
) -> str:
    """Build the writing stage system prompt."""
    parts: list[str] = []

    # Role
    parts.append(
        f"You are a narrative writer for an RPG world called '{world_name}'. "
        "Your task is to write immersive, engaging prose based on the generation plan "
        "provided to you. Follow the plan faithfully — do not add, remove, or change "
        "plot points, NPC actions, or outcomes."
    )

    # World tone
    if world_description:
        parts.append(
            f"## World\n\n{world_description}\n\n"
            "Use this description to inform the tone, atmosphere, and vocabulary of your writing."
        )

    # Character
    if character_name:
        char_text = f"## Player Character\n\n**{character_name}**"
        if character_description:
            char_text += f"\n\n{character_description}"
        parts.append(char_text)

    # Lore for consistency
    if lore_parts:
        parts.append(f"## World Context\n\n{lore_parts}")

    # Writing constraints
    parts.append(
        "## Writing Guidelines\n\n"
        "- Write in second person, present tense (addressing the player as \"you\")\n"
        "- Include all NPC dialogue specified in the plan\n"
        "- Describe actions, environments, and emotions vividly\n"
        "- Keep the narrative flowing naturally — don't list events mechanically\n"
        "- Your output is ONLY narrative prose\n"
        "- Do NOT include stat updates, JSON, tags, tool calls, or meta-information\n"
        "- Do NOT include [STAT_UPDATE] blocks — stats are handled separately"
    )

    # Admin style instructions
    if admin_prompt:
        parts.append(f"## Writing Style Instructions\n\n{admin_prompt}")

    # Player instructions
    if user_instructions:
        parts.append(f"## Player Instructions\n\n{user_instructions}")

    return "\n\n".join(parts)
