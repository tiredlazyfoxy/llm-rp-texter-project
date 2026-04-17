"""Stat update validation against world stat definitions.

PURPOSE
    Validates [STAT_UPDATE] parsed entries against WorldStatDefinition constraints.
    Applies valid updates to character_stats / world_stats dicts.

USAGE
    Called by simple_generation_service and chain_generation_service after
    parsing [STAT_UPDATE] blocks from LLM output.

DESIGN RATIONALE
    Separated from generation services to be reusable across all generation modes.
    Invalid updates are logged and silently skipped — never crash generation.

CHANGELOG
    stage3_step2a — Created
"""

import json
import logging
from typing import Any

from app.models.world import WorldStatDefinition

logger = logging.getLogger(__name__)


def validate_and_apply_stat_updates(
    updates: dict[str, Any],
    stat_defs: list[WorldStatDefinition],
    char_stats: dict[str, Any],
    world_stats: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate stat updates against definitions and apply valid ones.

    Args:
        updates: {stat_name: new_value} from _parse_stat_updates()
        stat_defs: WorldStatDefinition list for the world
        char_stats: current character stats dict
        world_stats: current world stats dict

    Returns:
        (new_char_stats, new_world_stats) with valid updates applied.
    """
    if not updates:
        return char_stats, world_stats

    new_char = dict(char_stats)
    new_world = dict(world_stats)

    # Build lookup by name
    defs_by_name: dict[str, WorldStatDefinition] = {d.name: d for d in stat_defs}

    for name, value in updates.items():
        stat_def = defs_by_name.get(name)
        if stat_def is None:
            logger.warning("Stat update skipped: unknown stat '%s'", name)
            continue

        validated = validate_single_value(stat_def, value)
        if validated is None:
            continue

        target = new_char if stat_def.scope.value == "character" else new_world
        target[name] = validated

    return new_char, new_world


def validate_single_value(
    stat_def: WorldStatDefinition, value: Any
) -> int | str | list[str] | None:
    """Validate a single stat value. Returns validated value or None if invalid."""
    stat_type = stat_def.stat_type.value

    if stat_type == "int":
        return _validate_int(stat_def, value)
    elif stat_type == "enum":
        return _validate_enum(stat_def, value)
    elif stat_type == "set":
        return _validate_set(stat_def, value)
    else:
        logger.warning("Stat update skipped: unknown type '%s' for '%s'", stat_type, stat_def.name)
        return None


def _validate_int(stat_def: WorldStatDefinition, value: Any) -> int | None:
    """Validate int stat: parse and clamp to [min, max]."""
    try:
        int_val = int(value)
    except (ValueError, TypeError):
        logger.warning(
            "Stat update skipped: '%s' value '%s' is not a valid integer",
            stat_def.name, value,
        )
        return None

    if stat_def.min_value is not None and int_val < stat_def.min_value:
        int_val = stat_def.min_value
        logger.debug("Stat '%s' clamped to min %d", stat_def.name, int_val)
    if stat_def.max_value is not None and int_val > stat_def.max_value:
        int_val = stat_def.max_value
        logger.debug("Stat '%s' clamped to max %d", stat_def.name, int_val)

    return int_val


def _validate_enum(stat_def: WorldStatDefinition, value: Any) -> str | None:
    """Validate enum stat: check value is in allowed list."""
    allowed = _parse_enum_values(stat_def)
    if allowed is None:
        return None

    str_val = str(value)
    if str_val not in allowed:
        logger.warning(
            "Stat update skipped: '%s' value '%s' not in allowed values %s",
            stat_def.name, str_val, allowed,
        )
        return None

    return str_val


def _validate_set(stat_def: WorldStatDefinition, value: Any) -> list[str] | None:
    """Validate set stat: parse as list, filter to valid elements."""
    allowed = _parse_enum_values(stat_def)
    if allowed is None:
        return None

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [value]

    if not isinstance(value, list):
        logger.warning(
            "Stat update skipped: '%s' value '%s' is not a list",
            stat_def.name, value,
        )
        return None

    valid_elements = [str(v) for v in value if str(v) in allowed]
    skipped = [str(v) for v in value if str(v) not in allowed]
    if skipped:
        logger.warning(
            "Stat '%s': filtered out invalid set elements %s", stat_def.name, skipped,
        )

    return valid_elements


def _parse_enum_values(stat_def: WorldStatDefinition) -> set[str] | None:
    """Parse enum_values JSON from stat definition."""
    if not stat_def.enum_values:
        logger.warning(
            "Stat update skipped: '%s' has no enum_values defined", stat_def.name,
        )
        return None
    try:
        values = json.loads(stat_def.enum_values)
        return set(str(v) for v in values)
    except json.JSONDecodeError:
        logger.warning(
            "Stat update skipped: '%s' has invalid enum_values JSON", stat_def.name,
        )
        return None
