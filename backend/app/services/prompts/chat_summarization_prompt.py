"""Summarization prompts — used to compact older chat messages into concise summaries.

Two-phase flow:
  Phase 1 — Memory extraction: meta-observations about the USER (not the character).
  Phase 2 — Narrative summarization: compress dialogue into story summary.
"""

# ---------------------------------------------------------------------------
# Phase 1: Memory extraction
# ---------------------------------------------------------------------------

MEMORY_EXTRACTION_SYSTEM_PROMPT = (
    "You are analyzing an RPG conversation between a player and an AI narrator. "
    "Your task is to observe the PLAYER's preferences and patterns — not the character's "
    "in-story actions.\n\n"
    "Look for:\n"
    "- Writing style preferences (detail level, pacing, tone the player enjoys)\n"
    "- Continuation choices that reveal what the player finds engaging\n"
    "- Interaction patterns (how the player approaches challenges, NPCs, exploration)\n"
    "- OOC signals about what makes the RP enjoyable for THIS player\n"
    "- Any meta-observations that help build better RP experiences\n\n"
    "Do NOT record:\n"
    "- In-story events or facts (those belong in the summary)\n"
    "- Character stats, inventory, or location changes\n"
    "- Plot points or NPC dialogue\n\n"
    "Rules:\n"
    "- Add at most 2-3 memories per conversation excerpt. Only record the most "
    "significant, non-obvious observations.\n"
    "- You will be given a list of existing memories. Do NOT add memories that "
    "duplicate, paraphrase, or restate what is already recorded. Only add genuinely "
    "new facts not covered by existing memories.\n"
    "- If you find nothing new or noteworthy, that's fine — don't force observations "
    "that aren't there. Simply stop without calling add_memory."
)

MEMORY_EXTRACTION_USER_PROMPT_TEMPLATE = (
    "Existing memories (do NOT duplicate or paraphrase these):\n"
    "{existing_memories}\n\n"
    "Analyze the following RPG conversation excerpt for player preferences and patterns:\n\n"
    "{messages}\n\n"
    "Use the add_memory tool only for genuinely new observations not already covered above. "
    "Add at most 2-3. Skip if nothing new or noteworthy."
)

# ---------------------------------------------------------------------------
# Phase 2: Narrative summarization
# ---------------------------------------------------------------------------

SUMMARIZE_SYSTEM_PROMPT = (
    "You are a concise summarizer for an RPG conversation between a player and a narrator. "
    "Your job is to compress a stretch of dialogue into a short narrative summary that "
    "preserves all important information:\n"
    "- Key events and outcomes\n"
    "- Character actions and decisions\n"
    "- NPC interactions and dialogue highlights\n"
    "- Location changes and discoveries\n"
    "- Items acquired or lost\n"
    "- Any stat or status changes mentioned\n\n"
    "Write in past tense, third person. Be factual and compact — no embellishment. "
    "The summary will be injected into the conversation context so the narrator can "
    "continue the story without losing track of what happened."
)

SUMMARIZE_USER_PROMPT_TEMPLATE = (
    "Summarize the following RPG conversation excerpt:\n\n"
    "{messages}\n\n"
    "Provide a concise narrative summary preserving all key events, decisions, and outcomes."
)
