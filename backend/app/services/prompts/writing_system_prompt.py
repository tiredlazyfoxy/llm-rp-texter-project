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

DESIGN RATIONALE
    Receives minimal context — most world data was already processed by the
    planning stage. Focuses on tone, style, and narrative quality.

CHANGELOG
    stage3_step1 — Skeleton created (returns empty string)
"""


def build_writing_system_prompt(
    world_name: str,
    world_description: str,
    character_name: str,
    character_description: str,
    lore_parts: str,
    admin_prompt: str,
) -> str:
    """Placeholder — returns empty string until step 2."""
    return ""
