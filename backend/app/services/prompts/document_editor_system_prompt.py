"""Document Editor System Prompt.

PURPOSE
-------
Provides the system prompt for the LLM-assisted document editor. The editor chat panel
sends this as the system message when an admin/editor is editing a world document
(location, NPC, or lore fact) and wants LLM help writing or revising content.

USAGE
-----
- Service file: ``app.services.prompts``
- Function: ``build_document_editor_system()``
- Stage introduced: Stage 1 Step 5
- Caller: ``app.routes.llm_chat.chat_stream`` — builds the system prompt before
  streaming the LLM response back to the document edit page.

VARIABLES (function params)
---------------------------
- ``doc_type`` — "location" | "npc" | "lore_fact"; comes from the frontend request.
- ``world_name`` — ``World.name`` from DB.
- ``world_description`` — ``World.description`` from DB.
- ``world_lore`` — ``World.lore`` concatenated with all ``WorldLoreFact.content``
  entries for the world, joined by double newlines.
- ``current_content`` — The current text in the document editor textarea, sent from
  the frontend with each request.

DESIGN RATIONALE
----------------
The prompt keeps the LLM focused on producing document content (not chat), and anchors
it in the world's setting. Current document content is included so the LLM can suggest
edits in context rather than writing from scratch. World lore provides background facts
the LLM should be consistent with.

CHANGELOG
---------
- v1 (stage1_step5): Initial version — role, world context, current content, instructions.
"""

_DOC_TYPE_LABELS = {
    "location": "Location",
    "npc": "NPC",
    "lore_fact": "Lore Fact",
}


def build_document_editor_system(
    doc_type: str,
    world_name: str,
    world_description: str,
    world_lore: str,
    current_content: str,
    enable_tools: bool = False,
) -> str:
    """Build the system prompt for the document editor LLM chat."""
    label = _DOC_TYPE_LABELS.get(doc_type, doc_type)

    sections: list[str] = [
        f"You are assisting an editor who is writing a {label} document "
        f"for the tabletop RPG world \"{world_name}\".",
        "Your task is to help draft, revise, and improve the document content. "
        "Respond with the text that should go into the document. "
        "Use markdown formatting where appropriate.",
    ]

    if world_description:
        sections.append(f"## World Description\n\n{world_description}")

    if world_lore:
        sections.append(f"## World Lore\n\n{world_lore}")

    if current_content:
        sections.append(
            f"## Current Document Content\n\n{current_content}\n\n"
            "The editor may ask you to rewrite, extend, or revise the above content. "
            "When providing a full replacement, output the complete updated text."
        )
    else:
        sections.append(
            "The document is currently empty. The editor will ask you to help "
            "draft initial content."
        )

    if enable_tools:
        sections.append(
            "## How to Use Your Tools\n\n"
            "World lore is NOT included in this prompt — you must look it up actively.\n"
            "You have up to 15 tool call rounds. Use them aggressively.\n\n"
            "**Strategy — research first, write last:**\n"
            "1. Run multiple searches before writing anything. "
            "Cast a wide net: try different queries, different source types.\n"
            "2. When a result mentions something relevant (a name, place, faction, event), "
            "immediately search for that too. Follow the threads.\n"
            "3. Cross-reference: if search() returns a location, also get_lore() on related topics.\n"
            "4. Only write the document after you feel you have a complete picture.\n\n"
            "**Tools:**\n"
            "- **search(query, source_type?)** — Semantic search across all world documents. "
            "source_type: 'location', 'npc', 'lore_fact', or omit for all.\n"
            "- **get_lore(query)** — Targeted lore fact lookup. "
            "Use for specific background details, history, factions, rules.\n"
            "- **web_search(query)** — Real-world reference (history, architecture, mythology, etc.).\n\n"
            "Do not invent lore. If something is not in the world documents, say so or search the web."
        )

    return "\n\n".join(sections)
