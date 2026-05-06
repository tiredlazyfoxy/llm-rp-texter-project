"""Stat placeholders section helper — shared by editor system prompts.

PURPOSE
-------
Renders the world's `WorldStatDefinition` names as a markdown section that
the document / world-field editor LLMs see in their system prompt. The
section uses the literal `{USER:NAME}` / `{WORLD:NAME}` syntax (never a
substituted value) so the editor preserves placeholders verbatim when
generating prose.

USAGE
-----
- Service file: ``app.services.prompts.stat_placeholders_section``
- Function: ``build_stat_placeholders_section(stat_defs)``
- Stage introduced: Feature 012 step 003
- Callers:
  - ``build_document_editor_system()``
  - ``build_world_field_editor_system()``

DESIGN
------
- Mirrors the bulleted-markdown shape Feature 010 used for runtime
  placeholders in these same prompts (one bullet per token, backticked
  literal).
- Hidden stats are still listed: `WorldStatDefinition.hidden` only gates
  the player-facing stats panel; placeholders still resolve at chat
  runtime regardless.
- Zero stat defs → return empty string so the caller can omit the section
  entirely (no "no stats defined" line; matches how empty world
  description / lore sections are simply skipped).
- Pure / no DB / no I/O. The function MUST NOT call
  ``apply_runtime_placeholders`` — editor prompts only emit literal text.
"""

from __future__ import annotations

from app.models.world import StatScope, WorldStatDefinition


_INTRO = (
    "## Stat Placeholders\n\n"
    "You may write the following uppercase tokens literally into the "
    "content. They substitute at chat time against the live chat's stat "
    "values, before the player ever sees the text. Preserve them "
    "verbatim — write the literal braces and uppercase letters exactly "
    "as shown. Lowercase variants are not recognized."
)


def _kind_label(stat: WorldStatDefinition) -> str:
    """Render the stat's kind in a way that hints at the substitution shape."""
    return stat.stat_type.value


def build_stat_placeholders_section(stat_defs: list[WorldStatDefinition]) -> str:
    """Render the editor-facing stat placeholders section.

    Returns an empty string when ``stat_defs`` is empty so callers can
    skip the section (caller should ``if section: sections.append(section)``).

    Hidden stats (``WorldStatDefinition.hidden``) are still listed —
    substitution at chat runtime is unaffected by the hidden flag.
    """
    if not stat_defs:
        return ""

    user_stats = [s for s in stat_defs if s.scope == StatScope.character]
    world_stats = [s for s in stat_defs if s.scope == StatScope.world]

    parts: list[str] = [_INTRO]

    if user_stats:
        parts.append("**User stats:**")
        bullets = [
            f"- `{{USER:{s.name}}}` — {_kind_label(s)}"
            for s in user_stats
        ]
        parts.append("\n".join(bullets))

    if world_stats:
        parts.append("**World stats:**")
        bullets = [
            f"- `{{WORLD:{s.name}}}` — {_kind_label(s)}"
            for s in world_stats
        ]
        parts.append("\n".join(bullets))

    return "\n\n".join(parts)
