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
    feature_012_step_004 — Added apply_admin_stat_updates(): admin-endpoint
        entrypoint that reuses validate_single_value but raises HTTPException
        on errors (vs the LLM path's silent skip).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.db import chats as chats_db
from app.db import stat_defs as stat_defs_db
from app.models.schemas.chat import StatUpdateItem
from app.models.world import StatScope, WorldStatDefinition

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


# ---------------------------------------------------------------------------
# Admin endpoint entrypoint (Feature 012, step 004)
# ---------------------------------------------------------------------------


def _all_stats_snapshot(
    char_stats: dict[str, Any],
    world_stats: dict[str, Any],
) -> dict[str, str]:
    """Stringified merged stat snapshot for error payloads.

    Mirrors the `all_stats` field shape produced by the LLM
    `update_stat` tool so admin and tool error bodies are
    interchangeable.
    """
    merged: dict[str, str] = {}
    merged.update({k: str(v) for k, v in char_stats.items()})
    merged.update({k: str(v) for k, v in world_stats.items()})
    return merged


def _expected_owner_for(stat_def: WorldStatDefinition) -> str:
    return "user" if stat_def.scope == StatScope.character else "world"


async def apply_admin_stat_updates(
    chat_id: int,
    updates: list[StatUpdateItem],
) -> list[StatUpdateItem]:
    """Apply a batch of admin-authored stat updates to a chat.

    Reuses `validate_single_value` (the same per-value validator the
    LLM `update_stat` tool calls) for type/range/enum/set checks. Any
    error short-circuits with `HTTPException(422, detail=<llm-tool
    error shape>)` — the response body matches the
    `{"status": "ERROR", "reason": ..., "all_stats": ...}` shape the
    `update_stat` tool surfaces today.

    On success, persists the new stat dicts atomically via
    `chats_db.update_session_stats` and returns the input list back
    so the caller can echo it to the admin client (step 006 reads
    the applied state from this echo — no SSE emit).
    """
    chat = await chats_db.get_session_by_id(chat_id)
    if chat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found",
        )

    stat_defs = await stat_defs_db.list_by_world(chat.world_id)
    defs_by_name: dict[str, WorldStatDefinition] = {d.name: d for d in stat_defs}

    char_stats = chats_db.parse_stats(chat.character_stats)
    world_stats = chats_db.parse_stats(chat.world_stats)

    # Pre-validate every item before mutating: any error aborts the
    # whole batch (admin endpoint is all-or-nothing — unlike the LLM
    # tool path which silently skips invalid entries).
    for item in updates:
        stat_def = defs_by_name.get(item.name)
        if stat_def is None:
            valid_names = sorted(defs_by_name.keys())
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "ERROR",
                    "reason": (
                        f"Stat '{item.name}' is not recognized. "
                        f"Valid stats: {', '.join(valid_names)}"
                    ),
                    "all_stats": _all_stats_snapshot(char_stats, world_stats),
                },
            )

        expected_owner = _expected_owner_for(stat_def)
        if item.owner != expected_owner:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "ERROR",
                    "reason": (
                        f"Stat '{item.name}' belongs to owner "
                        f"'{expected_owner}', not '{item.owner}'."
                    ),
                    "all_stats": _all_stats_snapshot(char_stats, world_stats),
                },
            )

        validated = validate_single_value(stat_def, item.value)
        if validated is None:
            stat_type = stat_def.stat_type.value
            if stat_type == "int":
                hint = "Expected integer"
                if stat_def.min_value is not None or stat_def.max_value is not None:
                    hint += f" in range [{stat_def.min_value}, {stat_def.max_value}]"
            elif stat_type == "enum":
                hint = f"Expected one of: {stat_def.enum_values}"
            elif stat_type == "set":
                hint = f"Expected list from: {stat_def.enum_values}"
            else:
                hint = f"Unknown stat type '{stat_type}'"
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "ERROR",
                    "reason": (
                        f"Value '{item.value}' is invalid for "
                        f"'{item.name}' ({stat_type}). {hint}"
                    ),
                    "all_stats": _all_stats_snapshot(char_stats, world_stats),
                },
            )

    # All items valid — apply via the existing validate-and-apply
    # helper so the persistence path is identical to the LLM tool's.
    plain_updates: dict[str, Any] = {item.name: item.value for item in updates}
    new_char, new_world = validate_and_apply_stat_updates(
        plain_updates, stat_defs, char_stats, world_stats,
    )

    persisted = await chats_db.update_session_stats(
        session_id=chat_id,
        character_stats_json=chats_db.serialize_stats(new_char),
        world_stats_json=chats_db.serialize_stats(new_world),
        modified_at=datetime.now(timezone.utc),
    )
    if not persisted:
        # Race: the chat row was deleted between our load and persist.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found",
        )

    logger.info(
        "Admin stat update applied: chat_id=%d, updates=%d", chat_id, len(updates),
    )
    return updates


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
