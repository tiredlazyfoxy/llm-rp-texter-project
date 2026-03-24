"""Chat CRUD service — sessions, messages, memories, rewind."""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.db import chats as chats_db
from app.db import locations as locations_db
from app.db import stat_defs as stat_defs_db
from app.db import worlds as worlds_db
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.chat_state_snapshot import ChatStateSnapshot
from app.models.world import WorldStatDefinition
from app.models.schemas.chat import (
    ChatDetailResponse,
    ChatMessageResponse,
    ChatSessionListItem,
    ChatSessionResponse,
    ChatStateSnapshotResponse,
    ChatSummaryResponse,
    LocationBrief,
    ModelConfig,
    StatDefinitionResponse,
    ToolCallInfo,
    WorldInfoResponse,
)
from app.services import snowflake as snowflake_svc

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

async def _get_hidden_stat_names(world_id: int) -> set[str]:
    """Return set of stat names marked as hidden for a world."""
    defs = await stat_defs_db.list_by_world(world_id)
    return {d.name for d in defs if d.hidden}


def _filter_stats(
    stats: dict[str, int | str | list[str]],
    hidden_names: set[str],
) -> dict[str, int | str | list[str]]:
    """Remove hidden stat keys from a stats dict."""
    if not hidden_names:
        return stats
    return {k: v for k, v in stats.items() if k not in hidden_names}


def _model_config_from_session_tool(s: ChatSession) -> ModelConfig:
    return ModelConfig(
        model_id=s.tool_model_id,
        temperature=s.tool_temperature,
        repeat_penalty=s.tool_repeat_penalty,
        top_p=s.tool_top_p,
    )


def _model_config_from_session_text(s: ChatSession) -> ModelConfig:
    return ModelConfig(
        model_id=s.text_model_id,
        temperature=s.text_temperature,
        repeat_penalty=s.text_repeat_penalty,
        top_p=s.text_top_p,
    )


def _msg_to_response(m: ChatMessage) -> ChatMessageResponse:
    tool_calls: list[ToolCallInfo] | None = None
    if m.tool_calls:
        try:
            raw = json.loads(m.tool_calls)
            tool_calls = [
                ToolCallInfo(
                    tool_name=tc["tool_name"],
                    arguments=tc.get("arguments", {}),
                    result=tc.get("result", ""),
                )
                for tc in raw
            ]
        except Exception:
            tool_calls = None
    return ChatMessageResponse(
        id=str(m.id),
        role=m.role,
        content=m.content,
        turn_number=m.turn_number,
        tool_calls=tool_calls,
        generation_plan=m.generation_plan,
        thinking_content=m.thinking_content,
        is_active_variant=m.is_active_variant,
        created_at=m.created_at.isoformat(),
    )


def _snap_to_response(
    snap: ChatStateSnapshot,
    location_name: str | None,
    hidden_names: set[str] | None = None,
) -> ChatStateSnapshotResponse:
    char_stats = chats_db.parse_stats(snap.character_stats)
    world_stats = chats_db.parse_stats(snap.world_stats)
    if hidden_names:
        char_stats = _filter_stats(char_stats, hidden_names)
        world_stats = _filter_stats(world_stats, hidden_names)
    return ChatStateSnapshotResponse(
        turn_number=snap.turn_number,
        location_id=str(snap.location_id) if snap.location_id else None,
        location_name=location_name,
        character_stats=char_stats,
        world_stats=world_stats,
    )


async def _build_session_response(
    session: ChatSession,
    caller_role: str = "player",
) -> ChatSessionResponse:
    world = await worlds_db.get_by_id(session.world_id)
    world_name = world.name if world else ""
    location_name: str | None = None
    if session.current_location_id:
        loc = await locations_db.get_by_id(session.current_location_id)
        location_name = loc.name if loc else None

    char_stats = chats_db.parse_stats(session.character_stats)
    world_stats = chats_db.parse_stats(session.world_stats)
    if caller_role == "player":
        hidden = await _get_hidden_stat_names(session.world_id)
        char_stats = _filter_stats(char_stats, hidden)
        world_stats = _filter_stats(world_stats, hidden)

    return ChatSessionResponse(
        id=str(session.id),
        world_id=str(session.world_id),
        world_name=world_name,
        character_name=session.character_name,
        character_description=session.character_description,
        character_stats=char_stats,
        world_stats=world_stats,
        current_location_id=str(session.current_location_id) if session.current_location_id else None,
        current_location_name=location_name,
        current_turn=session.current_turn,
        status=session.status,
        tool_model=_model_config_from_session_tool(session),
        text_model=_model_config_from_session_text(session),
        user_instructions=session.user_instructions,
        created_at=session.created_at.isoformat(),
        modified_at=session.modified_at.isoformat(),
    )


async def _build_detail_response(
    session: ChatSession,
    caller_role: str = "player",
) -> ChatDetailResponse:
    session_resp = await _build_session_response(session, caller_role)
    messages = await chats_db.list_active_messages(session.id)
    snapshots = await chats_db.list_snapshots(session.id)

    # Get hidden stat names for filtering (players only)
    hidden_names: set[str] | None = None
    if caller_role == "player":
        hidden_names = await _get_hidden_stat_names(session.world_id)

    # Build location name cache for snapshots
    location_cache: dict[int, str] = {}
    snap_responses: list[ChatStateSnapshotResponse] = []
    for snap in snapshots:
        loc_name: str | None = None
        if snap.location_id:
            if snap.location_id not in location_cache:
                loc = await locations_db.get_by_id(snap.location_id)
                location_cache[snap.location_id] = loc.name if loc else ""
            loc_name = location_cache[snap.location_id]
        snap_responses.append(_snap_to_response(snap, loc_name, hidden_names))

    variants: list[ChatMessageResponse] = []
    if session.current_turn > 0:
        variant_msgs = await chats_db.list_variants_for_turn(session.id, session.current_turn)
        variants = [_msg_to_response(m) for m in variant_msgs]

    summaries = await chats_db.list_summaries(session.id)
    summary_responses = [
        ChatSummaryResponse(
            id=str(s.id),
            start_message_id=str(s.start_message_id),
            end_message_id=str(s.end_message_id),
            start_turn=s.start_turn,
            end_turn=s.end_turn,
            content=s.content,
            created_at=s.created_at.isoformat(),
        )
        for s in summaries
    ]

    return ChatDetailResponse(
        session=session_resp,
        messages=[_msg_to_response(m) for m in messages],
        snapshots=snap_responses,
        variants=variants,
        summaries=summary_responses,
    )


def _init_stats_from_defs(defs: list[WorldStatDefinition]) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    for d in defs:
        val: int | str | list[str]
        if d.stat_type == "int":
            try:
                val = int(d.default_value)
            except (ValueError, TypeError):
                val = 0
        elif d.stat_type == "set":
            try:
                val = json.loads(d.default_value)
                if not isinstance(val, list):
                    val = []
            except Exception:
                val = []
        else:
            val = d.default_value or ""
        stats[d.name] = val
    return stats


def _extract_placeholders(template: str) -> list[str]:
    return re.findall(r"\{([A-Z_]+)\}", template)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Public API: list worlds
# ---------------------------------------------------------------------------

async def list_public_worlds(caller_id: int) -> list[WorldInfoResponse]:
    from app.models.world import WorldStatus
    worlds = await worlds_db.list_all()
    result: list[WorldInfoResponse] = []
    for w in worlds:
        if w.status == WorldStatus.draft or w.status == WorldStatus.archived:
            continue
        if w.status == WorldStatus.private and w.owner_id != caller_id:
            continue
        locs = await locations_db.list_by_world(w.id)
        stat_defs = await stat_defs_db.list_by_world(w.id)
        result.append(WorldInfoResponse(
            id=str(w.id),
            name=w.name,
            description=w.description,
            lore=w.lore,
            character_template=w.character_template,
            generation_mode=w.generation_mode or "simple",
            locations=[LocationBrief(id=str(loc.id), name=loc.name) for loc in locs],
            stat_definitions=[
                StatDefinitionResponse(
                    name=d.name,
                    description=d.description or "",
                    scope=d.scope.value,
                    stat_type=d.stat_type.value,
                    default_value=d.default_value or "",
                    min_value=d.min_value,
                    max_value=d.max_value,
                    enum_values=json.loads(d.enum_values) if d.enum_values else None,
                    hidden=d.hidden,
                )
                for d in stat_defs
            ],
        ))
    return result


# ---------------------------------------------------------------------------
# Public API: create session
# ---------------------------------------------------------------------------

async def create_chat(
    world_id: int,
    user_id: int,
    character_name: str,
    template_variables: dict[str, str],
    starting_location_id: int,
    tool_model: ModelConfig,
    text_model: ModelConfig,
) -> ChatSessionResponse:
    from app.models.world import WorldStatus

    world = await worlds_db.get_by_id(world_id)
    if world is None or world.status == WorldStatus.draft or world.status == WorldStatus.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found or not available")
    if world.status == WorldStatus.private and world.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="World is private")

    loc = await locations_db.get_by_id(starting_location_id)
    if loc is None or loc.world_id != world_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid starting location")

    # Build character description from template
    template = world.character_template or ""
    placeholders = _extract_placeholders(template)
    for ph in placeholders:
        if ph not in template_variables:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing template variable: {ph}",
            )
    char_description = template
    for ph, val in template_variables.items():
        char_description = char_description.replace(f"{{{ph}}}", val)

    # Initialize stats from world definitions
    stat_defs = await stat_defs_db.list_by_world(world_id)
    char_stats = _init_stats_from_defs([d for d in stat_defs if d.scope.value == "character"])
    world_stats = _init_stats_from_defs([d for d in stat_defs if d.scope.value == "world"])

    now = _now()
    session_id = snowflake_svc.generate_id()

    chat = ChatSession(
        id=session_id,
        user_id=user_id,
        world_id=world_id,
        current_location_id=starting_location_id,
        character_name=character_name,
        character_description=char_description,
        character_stats=chats_db.serialize_stats(char_stats),
        world_stats=chats_db.serialize_stats(world_stats),
        current_turn=0,
        status="active",
        tool_model_id=tool_model.model_id,
        tool_temperature=tool_model.temperature,
        tool_repeat_penalty=tool_model.repeat_penalty,
        tool_top_p=tool_model.top_p,
        text_model_id=text_model.model_id,
        text_temperature=text_model.temperature,
        text_repeat_penalty=text_model.repeat_penalty,
        text_top_p=text_model.top_p,
        user_instructions="",
        created_at=now,
        modified_at=now,
    )
    chat = await chats_db.create_session(chat)

    # Turn 0 snapshot
    snap_id = snowflake_svc.generate_id()
    snap = ChatStateSnapshot(
        id=snap_id,
        session_id=chat.id,
        turn_number=0,
        location_id=starting_location_id,
        character_stats=chats_db.serialize_stats(char_stats),
        world_stats=chats_db.serialize_stats(world_stats),
        created_at=now,
    )
    await chats_db.create_snapshot(snap)

    # Initial system message using world.initial_message
    initial_content = (world.initial_message or "").replace(
        "{character_name}", character_name
    ).replace(
        "{location_name}", loc.name
    ).replace(
        "{location_summary}", loc.content or "",
    )
    if initial_content:
        msg_id = snowflake_svc.generate_id()
        init_msg = ChatMessage(
            id=msg_id,
            session_id=chat.id,
            role="system",
            content=initial_content,
            turn_number=0,
            is_active_variant=True,
            created_at=now,
        )
        await chats_db.create_message(init_msg)

    return await _build_session_response(chat)


# ---------------------------------------------------------------------------
# Public API: list sessions
# ---------------------------------------------------------------------------

async def list_user_sessions(user_id: int) -> list[ChatSessionListItem]:
    sessions = await chats_db.list_sessions_by_user(user_id)
    result: list[ChatSessionListItem] = []
    for s in sessions:
        world = await worlds_db.get_by_id(s.world_id)
        location_name: str | None = None
        if s.current_location_id:
            loc = await locations_db.get_by_id(s.current_location_id)
            location_name = loc.name if loc else None
        result.append(ChatSessionListItem(
            id=str(s.id),
            world_id=str(s.world_id),
            world_name=world.name if world else "",
            character_name=s.character_name,
            current_location_name=location_name,
            current_turn=s.current_turn,
            status=s.status,
            modified_at=s.modified_at.isoformat(),
        ))
    return result


# ---------------------------------------------------------------------------
# Public API: get chat detail
# ---------------------------------------------------------------------------

async def get_chat_detail(
    session_id: int, user_id: int, caller_role: str = "player",
) -> ChatDetailResponse:
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return await _build_detail_response(chat, caller_role)


# ---------------------------------------------------------------------------
# Public API: update settings
# ---------------------------------------------------------------------------

async def update_settings(
    session_id: int,
    user_id: int,
    tool_model: ModelConfig | None,
    text_model: ModelConfig | None,
    user_instructions: str | None,
) -> None:
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    if tool_model is not None:
        chat.tool_model_id = tool_model.model_id
        chat.tool_temperature = tool_model.temperature
        chat.tool_repeat_penalty = tool_model.repeat_penalty
        chat.tool_top_p = tool_model.top_p
    if text_model is not None:
        chat.text_model_id = text_model.model_id
        chat.text_temperature = text_model.temperature
        chat.text_repeat_penalty = text_model.repeat_penalty
        chat.text_top_p = text_model.top_p
    if user_instructions is not None:
        chat.user_instructions = user_instructions
    chat.modified_at = _now()
    await chats_db.update_session(chat)


# ---------------------------------------------------------------------------
# Public API: archive / delete
# ---------------------------------------------------------------------------

async def archive_chat(session_id: int, user_id: int) -> None:
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    chat.status = "archived"
    chat.modified_at = _now()
    await chats_db.update_session(chat)


async def delete_chat(session_id: int, user_id: int) -> None:
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    await chats_db.delete_session(session_id)


# ---------------------------------------------------------------------------
# Public API: continue / rewind
# ---------------------------------------------------------------------------

async def continue_chat(session_id: int, user_id: int, selected_variant_id: int) -> None:
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    variant = await chats_db.get_message_by_id(selected_variant_id)
    if variant is None or variant.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid variant")
    await chats_db.delete_non_selected_variants(session_id, variant.turn_number, selected_variant_id)


async def rewind_chat(
    session_id: int, user_id: int, target_turn: int, caller_role: str = "player",
) -> ChatDetailResponse:
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    await chats_db.delete_summaries_after_turn(session_id, target_turn)
    await chats_db.delete_messages_after_turn(session_id, target_turn)
    await chats_db.delete_snapshots_after_turn(session_id, target_turn)

    # Restore state from snapshot at target_turn
    snap = await chats_db.get_snapshot_at_turn(session_id, target_turn)
    if snap:
        chat.character_stats = snap.character_stats
        chat.world_stats = snap.world_stats
        chat.current_location_id = snap.location_id

    chat.current_turn = target_turn
    chat.modified_at = _now()
    await chats_db.update_session(chat)

    return await _build_detail_response(chat, caller_role)


# ---------------------------------------------------------------------------
# Public API: memories
# ---------------------------------------------------------------------------

async def list_memories(session_id: int, user_id: int) -> list[ChatSummaryResponse]:
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    summaries = await chats_db.list_summaries(session_id)
    return [
        ChatSummaryResponse(
            id=str(s.id),
            start_message_id=str(s.start_message_id),
            end_message_id=str(s.end_message_id),
            start_turn=s.start_turn,
            end_turn=s.end_turn,
            content=s.content,
            created_at=s.created_at.isoformat(),
        )
        for s in summaries
    ]


async def get_summary_messages(
    session_id: int, summary_id: int, user_id: int,
) -> list[ChatMessageResponse]:
    """Get original messages for a specific summary (lazy load on expand)."""
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    summary = await chats_db.get_summary_by_id(summary_id)
    if summary is None or summary.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found")
    messages = await chats_db.list_messages_by_summary_id(summary_id)
    return [_msg_to_response(m) for m in messages]


async def delete_memory(session_id: int, memory_id: int, user_id: int) -> None:
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    deleted = await chats_db.delete_summary(memory_id, session_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")


# ---------------------------------------------------------------------------
# Public API: edit / delete message
# ---------------------------------------------------------------------------

async def edit_message(
    session_id: int, message_id: int, new_content: str, user_id: int,
    caller_role: str = "player",
) -> ChatDetailResponse:
    """Edit user message content and delete all subsequent messages/snapshots."""
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    msg = await chats_db.get_message_by_id(message_id)
    if msg is None or msg.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if msg.role != "user":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only edit user messages")
    if msg.summary_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot edit summarized messages")

    turn = msg.turn_number

    # Update content
    await chats_db.update_message_content(message_id, new_content)

    # Delete assistant messages at this turn + all messages after
    await chats_db.delete_messages_at_and_after_turn(session_id, turn, exclude_role="user")

    # Delete snapshots and summaries after previous turn
    await chats_db.delete_snapshots_after_turn(session_id, turn - 1)
    await chats_db.delete_summaries_after_turn(session_id, turn - 1)

    # Restore session state from snapshot at turn - 1
    snap = await chats_db.get_snapshot_at_turn(session_id, turn - 1)
    if snap:
        chat.character_stats = snap.character_stats
        chat.world_stats = snap.world_stats
        chat.current_location_id = snap.location_id

    chat.current_turn = turn - 1
    chat.modified_at = _now()
    await chats_db.update_session(chat)

    return await _build_detail_response(chat, caller_role)


async def delete_message(
    session_id: int, message_id: int, user_id: int,
    caller_role: str = "player",
) -> ChatDetailResponse:
    """Delete a message and all messages after it, then adjust session state."""
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    msg = await chats_db.get_message_by_id(message_id)
    if msg is None or msg.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if msg.role == "system":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete system messages")
    if msg.summary_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete summarized messages")

    turn = msg.turn_number
    import logging
    log = logging.getLogger(__name__)

    if msg.role == "user":
        # Delete this specific user message + all messages at turns strictly after
        log.info("delete_message: user msg id=%d at turn %d", msg.id, turn)
        await chats_db.delete_message_by_id(msg.id)
        await chats_db.delete_messages_at_and_after_turn(session_id, turn + 1)
        # Also delete assistant messages at this turn (they depend on this user message)
        await chats_db.delete_messages_at_and_after_turn(
            session_id, turn, exclude_role="user",
        )
        rewind_to = turn - 1
    else:
        # Delete this specific assistant + all messages at turns strictly after
        # Keep user message(s) at this turn
        log.info("delete_message: assistant msg id=%d at turn %d", msg.id, turn)
        await chats_db.delete_messages_at_and_after_turn(session_id, turn + 1)
        # Mark all assistant variants at this turn inactive
        variants = await chats_db.list_variants_for_turn(session_id, turn)
        for v in variants:
            if v.is_active_variant:
                await chats_db.set_message_inactive(v.id)
        rewind_to = turn - 1

    # Clean up snapshots/summaries and restore state
    log.info("delete_message: rewind_to=%d, cleaning snapshots/summaries after turn %d", rewind_to, rewind_to)
    await chats_db.delete_snapshots_after_turn(session_id, rewind_to)
    await chats_db.delete_summaries_after_turn(session_id, rewind_to)

    snap = await chats_db.get_snapshot_at_turn(session_id, rewind_to)
    if snap:
        chat.character_stats = snap.character_stats
        chat.world_stats = snap.world_stats
        chat.current_location_id = snap.location_id

    chat.current_turn = rewind_to
    chat.modified_at = _now()
    await chats_db.update_session(chat)

    remaining = await chats_db.list_active_messages(session_id)
    log.info("delete_message: done. current_turn=%d, remaining messages=%d", rewind_to, len(remaining))

    return await _build_detail_response(chat, caller_role)
