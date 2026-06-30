"""Retune system/instruction prompt builder.

PURPOSE
    Builds the system/instruction prompt for the in-chat preference *retune*
    LLM call (Feature 014). Given the existing tuning text for one dimension
    (plan_tuning or tone_tuning), the rejected feedback rows of a turn, and the
    finally accepted content, it instructs the model to produce a revised,
    concise tuning string that would have reduced the rejection.

USAGE
    Called by retune_service.maybe_retune once per targeted dimension, before
    the non-tool LLM completion. The returned string is the system prompt for
    that completion.

VARIABLES
    dimension          — Targeted tuning dimension label ("plan" or "text").
    current_tuning     — The existing tuning text for that dimension (may be "").
    rejections         — The turn's rejected ChatGenerationFeedback rows; each
                         carries scope, comment, and content_snapshot.
    accepted_content   — The finally accepted assistant content for the turn.

DESIGN RATIONALE
    One builder for both dimensions keeps the retune contract single-sourced;
    the dimension label lets the prompt frame the instruction (plan vs. tone)
    while reusing the same reject/accept evidence assembly.

CHANGELOG
    014_step004 — Skeleton created (raises NotImplementedError).
    014_step004 — Full prompt implementation.
"""

from app.models.chat_generation_feedback import ChatGenerationFeedback


def _truncate(text: str, limit: int = 1200) -> str:
    """Clip an evidence snapshot so the prompt stays concise."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " […]"


def build_retune_prompt(
    dimension: str,
    current_tuning: str,
    rejections: list[ChatGenerationFeedback],
    accepted_content: str,
) -> str:
    """Build the retune system/instruction prompt for one tuning dimension."""
    is_plan = dimension == "plan"
    if is_plan:
        dim_label = "plan-tuning"
        stage_desc = (
            "the PLANNING stage — the part of the pipeline that researches the "
            "world, decides plot beats, NPC reactions, and outcomes before any "
            "prose is written. Plan-tuning steers WHAT happens, not how it reads."
        )
    else:
        dim_label = "tone-tuning"
        stage_desc = (
            "the WRITING stage — the part of the pipeline that turns the plan "
            "into narrative prose. Tone-tuning steers HOW the text reads "
            "(voice, style, pacing, detail), not what happens in the plot."
        )

    parts: list[str] = []

    parts.append(
        "You maintain a short, persistent preference instruction that is injected "
        f"into {stage_desc}\n\n"
        f"Your task: revise the {dim_label} instruction so that the rejection(s) "
        "below would have been less likely. Infer the user's preference from what "
        "they rejected, the comments they left, and the content they finally "
        "accepted."
    )

    current = (current_tuning or "").strip()
    if current:
        parts.append(f"## Current {dim_label}\n\n{current}")
    else:
        parts.append(f"## Current {dim_label}\n\n(none yet — start from scratch)")

    reject_parts: list[str] = ["## Rejected generation(s)"]
    if rejections:
        for i, rej in enumerate(rejections, start=1):
            block: list[str] = [f"### Rejection {i}"]
            if rej.scope:
                block.append(f"- Attributed to: {rej.scope}")
            if rej.comment:
                block.append(f"- User comment: {rej.comment}")
            else:
                block.append("- User comment: (none)")
            block.append(f"- Rejected content:\n{_truncate(rej.content_snapshot)}")
            reject_parts.append("\n".join(block))
    else:
        reject_parts.append("(none)")
    parts.append("\n\n".join(reject_parts))

    parts.append(f"## Finally accepted content\n\n{_truncate(accepted_content)}")

    parts.append(
        f"## Output\n\n"
        f"Return ONLY the revised {dim_label} instruction as plain text — no "
        "preamble, no quotes, no explanation. Keep it concise (a few short "
        "sentences or bullet directives). It must read as standing guidance for "
        "future turns, not as commentary on this specific turn. Preserve any "
        "still-valid guidance from the current instruction and merge in what the "
        "rejection teaches."
    )

    return "\n\n".join(parts)
