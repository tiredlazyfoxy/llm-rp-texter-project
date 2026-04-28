"""Writing plan message builder.

PURPOSE
    Formats the planning stage output into a user message for the writing LLM.
    Injects collected_data and decisions so the writer knows what to narrate.

USAGE
    Called by chain_generation_service to build the plan injection message
    that is sent as context to the writing LLM.

VARIABLES
    collected_data — Free-text summary of data gathered by the planning agent
    decisions      — List of decisions made by the planning agent

DESIGN RATIONALE
    Kept as a separate template so the format can evolve independently
    of the system prompt. The writing LLM sees this as a user message
    containing the plan it should narrate.

CHANGELOG
    stage3_step1 — Skeleton created (returns empty string)
    stage3_step2b — Full template implementation
"""


def build_writing_plan_message(
    collected_data: str,
    decisions: list[str],
    location_name: str = "",
    present_npcs: str = "",
    current_stats: str = "",
) -> str:
    """Format planning output as a user message for the writing LLM."""
    parts = ["## Generation Plan"]

    # Structural scene context — always present, not dependent on LLM output
    scene_parts = []
    if location_name:
        scene_parts.append(f"**Location:** {location_name}")
    if present_npcs:
        scene_parts.append(f"**NPCs present:**\n{present_npcs}")
    if current_stats:
        scene_parts.append(f"**Stats:**\n{current_stats}")
    if scene_parts:
        parts.append("### Current Scene\n\n" + "\n\n".join(scene_parts))

    # Plan context from planning agent
    if collected_data:
        parts.append(f"### Context\n\n{collected_data}")

    # Decisions
    decision_list = "\n".join(f"- {d}" for d in decisions) if decisions else "- (no specific decisions)"
    parts.append(f"### What Happens This Turn\n\n{decision_list}")

    return "\n\n".join(parts)
