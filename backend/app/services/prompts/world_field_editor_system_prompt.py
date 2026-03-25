"""World Field Editor System Prompt.

PURPOSE
-------
Provides the system prompt for the LLM-assisted world field editor. Used when an
admin/editor wants LLM help writing or revising a world-level text field
(description, system_prompt, or initial_message) rather than a document.

USAGE
-----
- Service file: ``app.services.prompts``
- Function: ``build_world_field_editor_system()``
- Caller: ``app.routes.llm_chat.chat_stream`` — when ``field_type`` is set on the request.

VARIABLES (function params)
---------------------------
- ``field_type`` — "description" | "system_prompt" | "initial_message"
- ``world_name`` — ``World.name`` from DB.
- ``world_description`` — ``World.description`` from DB (omitted when editing description itself).
- ``world_lore`` — Concatenated lore facts (injected into prompt when tools disabled).
- ``injected_lore`` — Always-injected lore facts.
- ``current_content`` — Current value of the field being edited.
- ``enable_tools`` — Whether tool calling is active.

DESIGN RATIONALE
----------------
Each field has a distinct purpose so the role statement is field-specific.
World description is included as background for system_prompt and initial_message
editing, but omitted when editing the description itself to avoid circular context.
"""

_FIELD_ROLES = {
    "description": (
        "You are helping write the **world description** for the tabletop RPG world \"{world_name}\". "
        "This is the narrative overview of the setting — used for editor orientation and as background "
        "context in the LLM system prompt."
    ),
    "system_prompt": (
        "You are helping write the **LLM system prompt** for the tabletop RPG world \"{world_name}\". "
        "This text is injected as the system message in every player chat session. "
        "It defines the AI narrator's persona, tone, rules of engagement, and how the world is presented to players."
    ),
    "initial_message": (
        "You are helping write the **initial message** for the tabletop RPG world \"{world_name}\". "
        "This is the first message players see when they start a new chat session. "
        "Available placeholders: `{{character_name}}`, `{{location_name}}`, `{{location_summary}}`."
    ),
    "pipeline_prompt": (
        "You are helping write a **pipeline stage prompt** for the RPG world \"{world_name}\". "
        "This prompt is the system message for a generation step. "
        "The admin uses {{PLACEHOLDER}} syntax to inject runtime data. "
        "Each placeholder is an injection point — the code formats the data, the prompt just marks where it goes.\n\n"
        "Available placeholders:\n"
        "- {{WORLD_NAME}} — World display name\n"
        "- {{RULES}} — Numbered world rules\n"
        "- {{INJECTED_LORE}} — Always-injected lore facts\n"
        "- {{LOCATION}} — Full location block: name, description, exits, NPCs present\n"
        "- {{CHARACTER_NAME}} — Player character name\n"
        "- {{CHARACTER_STATS}} — Character-scope stats: definitions + current values\n"
        "- {{WORLD_STATS}} — World-scope stats: definitions + current values\n"
        "- {{USER_INSTRUCTIONS}} — Player instructions\n"
        "- {{TURN_FACTS}} — Collected context/facts from previous tool steps (chain mode writer only)\n"
        "- {{TURN_DECISIONS}} — Decisions/outcomes to execute from previous tool steps (chain mode writer only)\n"
        "- {{TOOLS}} — Auto-generated list of available tools\n\n"
        "Write the prompt using these placeholders where appropriate. "
        "Use markdown headers to organize sections. "
        "Empty placeholders resolve to empty string at runtime."
    ),
}

_FIELD_LABELS = {
    "description": "World Description",
    "system_prompt": "System Prompt",
    "initial_message": "Initial Message",
    "pipeline_prompt": "Pipeline Stage Prompt",
}


def build_world_field_editor_system(
    field_type: str,
    world_name: str,
    world_description: str,
    world_lore: str,
    current_content: str,
    enable_tools: bool = False,
    injected_lore: str = "",
) -> str:
    """Build the system prompt for the world field editor LLM chat."""
    role_template = _FIELD_ROLES.get(
        field_type,
        "You are helping write a text field for the tabletop RPG world \"{world_name}\".",
    )
    role_line = role_template.format(world_name=world_name)
    field_label = _FIELD_LABELS.get(field_type, field_type)

    sections: list[str] = [
        role_line,
        "Your task is to help draft, revise, and improve this field. "
        "Respond with the text that should go into the field. "
        "Use markdown formatting where appropriate.",
    ]

    # Include world description as background context — except when editing it
    if world_description and field_type != "description":
        sections.append(f"## World Description\n\n{world_description}")

    # Always-injected lore facts appear regardless of tools mode
    if injected_lore:
        sections.append(f"## World Context\n\n{injected_lore}")

    if world_lore:
        sections.append(f"## World Lore\n\n{world_lore}")

    if current_content:
        sections.append(
            f"## Current {field_label}\n\n{current_content}\n\n"
            "The editor may ask you to rewrite, extend, or revise the above content. "
            "When providing a full replacement, output the complete updated text."
        )
    else:
        sections.append(
            f"The {field_label} is currently empty. The editor will ask you to help "
            "draft initial content."
        )

    if enable_tools:
        sections.append(
            "## How to Use Your Tools\n\n"
            "World lore is NOT included in this prompt — you must look it up actively.\n"
            "You have up to 15 tool call rounds. Use them aggressively.\n\n"
            "**Strategy — research first, write last:**\n"
            "1. Start with world searches: search() and get_lore() to understand what already exists.\n"
            "2. Then use web_search() for real-world reference material — do this proactively, "
            "not just as a fallback. Good writing is grounded in real detail.\n"
            "3. When a result mentions something relevant (a name, place, faction, event), "
            "follow the thread with another search.\n"
            "4. Only write after you have both world context and real-world grounding.\n\n"
            "**Tools:**\n"
            "- **search(query, source_type?)** — Semantic search across all world documents. "
            "source_type: 'location', 'npc', 'lore_fact', or omit for all.\n"
            "- **get_lore(query)** — Targeted lore fact lookup. "
            "Use for specific background details, history, factions, rules.\n"
            "- **web_search(query)** — Use proactively for any real-world knowledge that would "
            "enrich the content: historical periods, cultural practices, architectural styles, "
            "naming conventions, mythology, material culture, trade goods, daily life details. "
            "Do not rely on memory — call web_search whenever real-world grounding would help.\n\n"
            "Do not invent world lore. If something is not in the world documents, say so or use get_lore/search."
        )

    return "\n\n".join(sections)
