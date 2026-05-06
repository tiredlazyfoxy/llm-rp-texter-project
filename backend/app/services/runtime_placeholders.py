"""Pure runtime placeholder substitution helper.

PURPOSE
    Single, centralized substitution of the runtime placeholder tokens
    recognized inside player-facing text:

        {CHARACTER_NAME}    -> session character name
        {LOCATION_NAME}     -> current (or starting) location name
        {LOCATION_SUMMARY}  -> current (or starting) location content
        {USER:NAME}         -> live character-scope stat value
        {WORLD:NAME}        -> live world-scope stat value

    Every chat-runtime substitution site (chat_service initial_message,
    chat_context location/lore/NPC content, chat_tools wrappers) calls
    this helper. No other module re-implements the .replace() logic.

DESIGN RATIONALE
    Lives in `services/` because both `chat_service.py` and
    `chat_context.py` consume it; placing it in `db/` would invert the
    layering. The helper is pure -- no I/O, no DB, no imports from
    `app.db.*` -- so keeping it here does not violate layer separation.

    Distinct from `app.db.worlds.rewrite_initial_message_tokens()`
    (introduced in feature 010 step 001), which performs a one-time
    source-data lowercase-to-uppercase normalization on stored
    `World.initial_message` rows. That helper edits the data; this
    helper substitutes runtime values into already-normalized text.
"""

import json
import logging
import re
from typing import TypedDict

from app.models.world import StatScope, StatType, WorldStatDefinition

logger = logging.getLogger(__name__)


# Stat values are stored on ChatStateSnapshot as JSON dicts whose values
# are already typed by stat_validation.validate_single_value:
#   int  stats  -> int
#   enum stats  -> str
#   set  stats  -> list[str]
# We carry that exact shape on the runtime context so the helper stays
# pure (no JSON parsing, no DB lookup) and the typing stays precise.
StatValue = int | str | list[str]


class RuntimePlaceholderContext(TypedDict, total=False):
    # Feature 010 fields (still required at every call site that builds
    # the context; total=False only relaxes the type-checker contract so
    # the new optional stat fields can be omitted by editor-mode dummies).
    character_name: str
    location_name: str
    location_summary: str
    # Feature 012 stat fields. `stat_definitions` carries the world's
    # WorldStatDefinition rows (used for kind/iteration-order lookup);
    # `stat_values` is a precomputed `(owner, name) -> value` map keyed
    # by namespace prefix so the regex pass is O(1) per token. owner is
    # "user" (character scope) or "world" (world scope); name matches
    # WorldStatDefinition.name (uppercase, case-sensitive).
    stat_definitions: list[WorldStatDefinition] | None
    stat_values: dict[tuple[str, str], StatValue] | None


# Matches namespaced stat tokens like {USER:HEALTH} / {WORLD:WEATHER}.
# - owner group is constrained to USER|WORLD (other namespaces survive
#   untouched so future widening stays opt-in).
# - name group requires uppercase + digits + underscore, leading
#   non-digit, matching WorldStatDefinition.name shape.
_STAT_TOKEN_RE = re.compile(r"\{(USER|WORLD):([A-Z_][A-Z0-9_]*)\}")


def apply_runtime_placeholders(
    text: str,
    ctx: RuntimePlaceholderContext | None,
) -> str:
    """Substitute runtime placeholder tokens in `text`.

        {CHARACTER_NAME}    -> ctx["character_name"]
        {LOCATION_NAME}     -> ctx["location_name"]
        {LOCATION_SUMMARY}  -> ctx["location_summary"]
        {USER:NAME}         -> live character-scope stat value
        {WORLD:NAME}        -> live world-scope stat value

    If `ctx` is None, returns `text` unchanged (editor-mode contract:
    leave literal tokens intact so the AI editor learns the syntax).

    Render rules for stat tokens (locked in feature 012 context.md):
        int   -> str(value)
        enum  -> the value as-is (already a string)
        set   -> ", ".join(values) using the WorldStatDefinition
                 enum_values declared order when available, else the
                 stored iteration order
        missing/unknown name -> "" + DEBUG log; never raises
        unknown owner namespace ({NPC:FOO}, ...) -> left untouched by
                 regex (only USER and WORLD are matched)

    Pure: no I/O. Idempotent on already-substituted text -- the helper
    only matches the literal uppercase token strings, so a second call
    on output that no longer contains those literals is a no-op.

    Lowercase variants like `{character_name}` / `{user:health}` are
    intentionally NOT substituted: the runtime contract is uppercase
    only (consistent with feature 010 step 001). Lowercase legacy
    tokens in stored data are handled by the one-time source-data
    migration.

    Pass ordering: namespaced stat pass runs before the literal-string
    Feature 010 replacements. Neither pattern can match the other's
    token shape (the literal tokens contain no `:` and the namespaced
    regex requires a `:`), so order is for clarity rather than
    correctness.
    """
    if ctx is None:
        return text

    text = _STAT_TOKEN_RE.sub(lambda m: _resolve_stat_token(m, ctx), text)

    return (
        text
        .replace("{CHARACTER_NAME}", ctx.get("character_name", ""))
        .replace("{LOCATION_NAME}", ctx.get("location_name", ""))
        .replace("{LOCATION_SUMMARY}", ctx.get("location_summary", ""))
    )


def _resolve_stat_token(
    match: re.Match[str], ctx: RuntimePlaceholderContext
) -> str:
    """Resolve a single `{USER:NAME}` / `{WORLD:NAME}` match.

    Returns "" and emits a DEBUG log on any miss (no definition, no
    value, unknown stat type). Never raises.
    """
    raw = match.group(0)
    owner_token = match.group(1)  # "USER" or "WORLD"
    name = match.group(2)
    owner = "user" if owner_token == "USER" else "world"

    stat_defs = ctx.get("stat_definitions") or []
    stat_values = ctx.get("stat_values") or {}

    stat_def = _find_stat_def(stat_defs, owner, name)
    if stat_def is None:
        logger.debug(
            "runtime placeholder unresolved (no definition): %s", raw
        )
        return ""

    if (owner, name) not in stat_values:
        logger.debug(
            "runtime placeholder unresolved (no value): %s", raw
        )
        return ""

    value = stat_values[(owner, name)]
    return _render_stat_value(stat_def, value, raw)


def _find_stat_def(
    stat_defs: list[WorldStatDefinition], owner: str, name: str
) -> WorldStatDefinition | None:
    """Linear scan for a definition matching (owner, name).

    Stat-def lists are small (tens of rows per world) so the cost is
    negligible and avoids forcing callers to precompute a second map.
    """
    for d in stat_defs:
        if d.name != name:
            continue
        def_owner = "user" if d.scope == StatScope.character else "world"
        if def_owner == owner:
            return d
    return None


def _render_stat_value(
    stat_def: WorldStatDefinition, value: StatValue, raw_token: str
) -> str:
    """Apply the locked render rule for a single stat type."""
    kind = stat_def.stat_type
    if kind == StatType.int_:
        if isinstance(value, bool):
            # bool is an int subclass in Python; coerce defensively.
            return str(int(value))
        if isinstance(value, int):
            return str(value)
        # Stored shape disagrees with the definition; fall back to str
        # rather than raising so a corrupted snapshot can't break a
        # generation pass.
        logger.debug(
            "runtime placeholder int kind got non-int value: %s",
            raw_token,
        )
        return str(value)
    if kind == StatType.enum_:
        return str(value)
    if kind == StatType.set_:
        if not isinstance(value, list):
            logger.debug(
                "runtime placeholder set kind got non-list value: %s",
                raw_token,
            )
            return ""
        return ", ".join(_iter_set_values(stat_def, value))
    logger.debug(
        "runtime placeholder unknown stat kind '%s': %s",
        kind, raw_token,
    )
    return ""


def build_stat_values_map(
    stat_defs: list[WorldStatDefinition],
    character_stats: dict[str, StatValue],
    world_stats: dict[str, StatValue],
) -> dict[tuple[str, str], StatValue]:
    """Compose the `(owner, name) -> value` map consumed by the helper.

    Pure builder shared by every chat-runtime entrypoint that wires
    stat snapshots onto a `RuntimePlaceholderContext`. Centralizing it
    keeps the StatScope -> owner-token mapping in one place and avoids
    re-deriving the (owner, name) keys at five call sites.

    Stats whose name has no matching definition are silently dropped:
    the helper's miss path already DEBUG-logs unknown names at render
    time, so dropping unknowns here is consistent with the "missing
    definition -> empty string" contract.
    """
    by_name: dict[str, WorldStatDefinition] = {d.name: d for d in stat_defs}
    out: dict[tuple[str, str], StatValue] = {}
    for name, value in character_stats.items():
        sd = by_name.get(name)
        if sd is None or sd.scope != StatScope.character:
            continue
        out[("user", name)] = value
    for name, value in world_stats.items():
        sd = by_name.get(name)
        if sd is None or sd.scope != StatScope.world:
            continue
        out[("world", name)] = value
    return out


def _iter_set_values(
    stat_def: WorldStatDefinition, value: list[str]
) -> list[str]:
    """Order set elements by the definition's declared enum_values.

    Falls back to the stored iteration order when the definition has
    no enum_values JSON or the JSON cannot be parsed.
    """
    if not stat_def.enum_values:
        return [str(v) for v in value]
    try:
        declared = json.loads(stat_def.enum_values)
    except (json.JSONDecodeError, TypeError):
        return [str(v) for v in value]
    if not isinstance(declared, list):
        return [str(v) for v in value]
    declared_str = [str(v) for v in declared]
    present = {str(v) for v in value}
    ordered = [v for v in declared_str if v in present]
    # Append any present-but-undeclared members preserving stored order
    # (defensive: lets a corrupted snapshot still render).
    extras = [str(v) for v in value if str(v) not in declared_str]
    return ordered + extras
