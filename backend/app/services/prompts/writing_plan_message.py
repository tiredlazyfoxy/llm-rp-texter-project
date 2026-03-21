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
"""


def build_writing_plan_message(
    collected_data: str,
    decisions: list[str],
) -> str:
    """Placeholder — returns empty string until step 2."""
    return ""
