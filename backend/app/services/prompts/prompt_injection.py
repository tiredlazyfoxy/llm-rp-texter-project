"""Prompt template resolution engine.

PURPOSE
    Resolves {PLACEHOLDER} patterns in admin-configured prompt templates
    with runtime values from chat context. Shared by both simple and chain
    generation modes.

USAGE
    resolve_prompt_template(template, WORLD_NAME="...", RULES="...", ...)
    build_tools_description(["get_location_info", "search", ...])
    format_facts([planning_ctx1, planning_ctx2])
    format_decisions([planning_ctx1, planning_ctx2])

CHANGELOG
    stage5_step2 — Created
"""

import re

from app.services.prompts.tool_catalog import TOOL_CATALOG


def resolve_prompt_template(template: str, **values: str) -> str:
    """Replace {UPPER_SNAKE_CASE} placeholders in a template with provided values.

    Unknown placeholders are left as-is. Empty values resolve to empty string.
    Consecutive blank lines (3+) are collapsed to 2 to clean up gaps from
    empty placeholders.
    """

    def replacer(match: re.Match) -> str:
        key = match.group(1)
        if key in values:
            return values[key]
        return match.group(0)  # leave unknown placeholders as-is

    result = re.sub(r"\{([A-Z_]+)\}", replacer, template)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def build_tools_description(tool_names: list[str]) -> str:
    """Format a list of tool names into a categorized description block.

    Looks up each name in TOOL_CATALOG and groups by category.
    Returns empty string if no matching tools.
    """
    catalog = {t["name"]: t for t in TOOL_CATALOG}

    # Group matching tools by category
    groups: dict[str, list[str]] = {}
    for name in tool_names:
        entry = catalog.get(name)
        if entry is None:
            continue
        category = entry["category"]
        if category not in groups:
            groups[category] = []
        groups[category].append(f"- `{name}` — {entry['description']}")

    if not groups:
        return ""

    # Order: research, action, planning, director
    category_order = ["research", "action", "planning", "director"]
    category_titles = {
        "research": "### Research Tools",
        "action": "### Action Tools",
        "planning": "### Planning Tools",
        "director": "### Director Tools",
    }

    parts: list[str] = []
    for cat in category_order:
        if cat in groups:
            parts.append(category_titles[cat])
            parts.append("\n".join(groups[cat]))

    return "\n\n".join(parts)


def format_facts(planning_contexts: list) -> str:
    """Collect all facts from planning contexts into a formatted string.

    Each fact on its own line as a bullet point.
    Returns empty string if no facts.
    """
    all_facts = [f for ctx in planning_contexts for f in ctx.facts]
    if not all_facts:
        return ""
    return "\n".join(f"- {fact}" for fact in all_facts)


def format_decisions(planning_contexts: list) -> str:
    """Collect all decisions from planning contexts into a formatted string.

    Each decision as a bullet point.
    Returns empty string if no decisions.
    """
    all_decisions = [d for ctx in planning_contexts for d in ctx.decisions]
    if not all_decisions:
        return ""
    return "\n".join(f"- {d}" for d in all_decisions)
