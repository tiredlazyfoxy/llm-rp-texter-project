"""Chat agent service — LLM generation, SSE streaming, stat updates."""

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.db import chats as chats_db
from app.db import worlds as worlds_db
from app.models.chat_message import ChatMessage
from app.models.chat_state_snapshot import ChatStateSnapshot
from app.models.schemas.chat import ChatMessageResponse
from app.services.llm_chat import get_llm_client_for_model
from app.services.prompts.chat_system_prompt import build_chat_system_prompt
from app.services import snowflake as snowflake_svc

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Stat helpers (stub — full implementation in stage 3)
# ---------------------------------------------------------------------------

def _parse_stat_updates(content: str) -> dict[str, Any]:
    """Extract [STAT_UPDATE] block from assistant response. Stub: returns empty dict."""
    match = re.search(r"\[STAT_UPDATE\](.*?)\[/STAT_UPDATE\]", content, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1).strip())
    except Exception:
        return {}


def _apply_stat_updates(
    character_stats: dict,
    world_stats: dict,
    updates: dict,
) -> tuple[dict, dict]:
    """Apply stat updates. Stub: returns stats unchanged."""
    return character_stats, world_stats


async def _build_llm_messages(session_id: int) -> list[dict[str, str]]:
    """Build LLM message list: summary blocks + non-summarized active messages."""
    from llm.message import LLMMessage

    llm_messages: list[LLMMessage] = []

    # Insert summary blocks
    summaries = await chats_db.list_summaries(session_id)
    for s in summaries:
        llm_messages.append({
            "role": "user",
            "content": f"[Summary of turns {s.start_turn}\u2013{s.end_turn}]:\n{s.content}",
        })

    # Non-summarized active messages (list_active_messages already filters summary_id IS NULL)
    active_msgs = await chats_db.list_active_messages(session_id)
    for m in active_msgs:
        if m.role in ("user", "assistant", "system"):
            llm_messages.append({
                "role": m.role if m.role in ("user", "assistant") else "user",
                "content": m.content,
            })

    return llm_messages


# ---------------------------------------------------------------------------
# SSE generation: generate_response
# ---------------------------------------------------------------------------

async def generate_response(
    session_id: int,
    user_id: int,
    user_message: str,
) -> AsyncGenerator[str, None]:
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    if chat.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chat is not active")

    model_id = chat.text_model_id
    if not model_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No text model configured")

    async def _stream() -> AsyncGenerator[str, None]:
        now = _now()
        turn = chat.current_turn + 1

        # Save user message
        user_msg_id = snowflake_svc.generate_id()
        user_msg = ChatMessage(
            id=user_msg_id,
            session_id=session_id,
            role="user",
            content=user_message,
            turn_number=turn,
            is_active_variant=True,
            created_at=now,
        )
        await chats_db.create_message(user_msg)

        # Build system prompt
        world = await worlds_db.get_by_id(chat.world_id)
        system_prompt = build_chat_system_prompt(
            world_name=world.name if world else "",
            world_description=world.description if world else "",
            world_lore=world.lore if world else "",
            character_name=chat.character_name,
            character_description=chat.character_description,
            user_instructions=chat.user_instructions,
        )

        # Build message history for LLM (summaries + non-summarized messages)
        llm_messages = await _build_llm_messages(session_id)

        client = await get_llm_client_for_model(model_id)

        options: dict = {
            "temperature": chat.text_temperature,
            "top_p": chat.text_top_p,
            "repeat_penalty": chat.text_repeat_penalty,
        }

        queue: asyncio.Queue[str | None] = asyncio.Queue()
        content_parts: list[str] = []
        in_thinking = False

        async def on_delta(delta: str) -> None:
            nonlocal in_thinking
            text = delta
            if not in_thinking and "<think>" in text:
                idx = text.index("<think>")
                before = text[:idx]
                after = text[idx + 7:]
                if before:
                    content_parts.append(before)
                    await queue.put(_sse("token", {"content": before}))
                in_thinking = True
                if after:
                    await queue.put(_sse("thinking", {"content": after}))
                return
            if in_thinking and "</think>" in text:
                idx = text.index("</think>")
                before = text[:idx]
                after = text[idx + 8:]
                if before:
                    await queue.put(_sse("thinking", {"content": before}))
                await queue.put(_sse("thinking_done", {}))
                in_thinking = False
                if after:
                    content_parts.append(after)
                    await queue.put(_sse("token", {"content": after}))
                return
            if in_thinking:
                await queue.put(_sse("thinking", {"content": text}))
            else:
                content_parts.append(text)
                await queue.put(_sse("token", {"content": text}))

        async def run_llm() -> None:
            try:
                async with client:
                    await client.chat(
                        llm_messages,
                        system=system_prompt,
                        options=options,
                        stream=True,
                        on_delta=on_delta,
                    )
                full_content = "".join(content_parts)

                # Parse stat updates (stub)
                updates = _parse_stat_updates(full_content)
                char_stats = chats_db.parse_stats(chat.character_stats)
                world_stats = chats_db.parse_stats(chat.world_stats)
                new_char, new_world = _apply_stat_updates(char_stats, world_stats, updates)

                # Save assistant message
                msg_id = snowflake_svc.generate_id()
                asst_msg = ChatMessage(
                    id=msg_id,
                    session_id=session_id,
                    role="assistant",
                    content=full_content,
                    turn_number=turn,
                    is_active_variant=True,
                    created_at=_now(),
                )
                await chats_db.create_message(asst_msg)

                # Update session state
                chat.current_turn = turn
                chat.character_stats = chats_db.serialize_stats(new_char)
                chat.world_stats = chats_db.serialize_stats(new_world)
                chat.modified_at = _now()
                await chats_db.update_session(chat)

                # Save snapshot
                snap_id = snowflake_svc.generate_id()
                snap = ChatStateSnapshot(
                    id=snap_id,
                    session_id=session_id,
                    turn_number=turn,
                    location_id=chat.current_location_id,
                    character_stats=chats_db.serialize_stats(new_char),
                    world_stats=chats_db.serialize_stats(new_world),
                    created_at=_now(),
                )
                await chats_db.create_snapshot(snap)

                if updates:
                    await queue.put(_sse("stat_update", {"stats": {**new_char, **new_world}}))

                # Strip [STAT_UPDATE] block from displayed content
                display_content = re.sub(
                    r"\[STAT_UPDATE\].*?\[/STAT_UPDATE\]", "", full_content, flags=re.DOTALL
                ).strip()

                msg_resp = ChatMessageResponse(
                    id=str(asst_msg.id),
                    role="assistant",
                    content=display_content,
                    turn_number=turn,
                    tool_calls=None,
                    is_active_variant=True,
                    created_at=asst_msg.created_at.isoformat(),
                )
                await queue.put(_sse("done", {"message": msg_resp.model_dump()}))
            except Exception as exc:
                logger.exception("Chat generation error")
                await queue.put(_sse("error", {"detail": str(exc)}))
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_llm())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            if not task.done():
                task.cancel()

    return _stream()


# ---------------------------------------------------------------------------
# SSE generation: regenerate_response
# ---------------------------------------------------------------------------

async def regenerate_response(
    session_id: int,
    user_id: int,
) -> AsyncGenerator[str, None]:
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    if chat.status != "active" or chat.current_turn == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot regenerate")

    model_id = chat.text_model_id
    if not model_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No text model configured")

    turn = chat.current_turn

    # Mark current active assistant message as inactive
    current_asst = await chats_db.get_active_assistant_at_turn(session_id, turn)
    if current_asst:
        await chats_db.set_message_inactive(current_asst.id)

    # Reload user message for this turn
    user_msg = await chats_db.get_user_message_at_turn(session_id, turn)
    user_content = user_msg.content if user_msg else ""

    # Restore stats from previous snapshot
    prev_snap = await chats_db.get_snapshot_at_turn(session_id, turn - 1)
    if prev_snap:
        chat.character_stats = prev_snap.character_stats
        chat.world_stats = prev_snap.world_stats
        await chats_db.update_session(chat)

    async def _stream() -> AsyncGenerator[str, None]:
        world = await worlds_db.get_by_id(chat.world_id)
        system_prompt = build_chat_system_prompt(
            world_name=world.name if world else "",
            world_description=world.description if world else "",
            world_lore=world.lore if world else "",
            character_name=chat.character_name,
            character_description=chat.character_description,
            user_instructions=chat.user_instructions,
        )

        from llm.message import LLMMessage
        # Build context with summaries + non-summarized messages (excludes current turn's assistant)
        all_llm = await _build_llm_messages(session_id)
        # Filter out messages from current turn (user message will be re-added)
        # _build_llm_messages includes everything active; we need to trim current turn
        # Rebuild: keep summary blocks + messages before current turn
        llm_messages: list[LLMMessage] = []
        summaries = await chats_db.list_summaries(session_id)
        for s in summaries:
            llm_messages.append({
                "role": "user",
                "content": f"[Summary of turns {s.start_turn}\u2013{s.end_turn}]:\n{s.content}",
            })
        all_active = await chats_db.list_active_messages(session_id)
        for m in all_active:
            if m.turn_number >= turn:
                continue
            if m.role in ("user", "assistant", "system"):
                llm_messages.append({
                    "role": m.role if m.role in ("user", "assistant") else "user",
                    "content": m.content,
                })
        # Add user message for current turn
        if user_content:
            llm_messages.append({"role": "user", "content": user_content})

        client = await get_llm_client_for_model(model_id)
        options: dict = {
            "temperature": chat.text_temperature,
            "top_p": chat.text_top_p,
            "repeat_penalty": chat.text_repeat_penalty,
        }

        queue: asyncio.Queue[str | None] = asyncio.Queue()
        content_parts: list[str] = []
        in_thinking = False

        async def on_delta(delta: str) -> None:
            nonlocal in_thinking
            text = delta
            if not in_thinking and "<think>" in text:
                idx = text.index("<think>")
                before, after = text[:idx], text[idx + 7:]
                if before:
                    content_parts.append(before)
                    await queue.put(_sse("token", {"content": before}))
                in_thinking = True
                if after:
                    await queue.put(_sse("thinking", {"content": after}))
                return
            if in_thinking and "</think>" in text:
                idx = text.index("</think>")
                before, after = text[:idx], text[idx + 8:]
                if before:
                    await queue.put(_sse("thinking", {"content": before}))
                await queue.put(_sse("thinking_done", {}))
                in_thinking = False
                if after:
                    content_parts.append(after)
                    await queue.put(_sse("token", {"content": after}))
                return
            if in_thinking:
                await queue.put(_sse("thinking", {"content": text}))
            else:
                content_parts.append(text)
                await queue.put(_sse("token", {"content": text}))

        async def run_llm() -> None:
            try:
                async with client:
                    await client.chat(
                        llm_messages,
                        system=system_prompt,
                        options=options,
                        stream=True,
                        on_delta=on_delta,
                    )
                full_content = "".join(content_parts)
                updates = _parse_stat_updates(full_content)
                char_stats = chats_db.parse_stats(chat.character_stats)
                world_stats_dict = chats_db.parse_stats(chat.world_stats)
                new_char, new_world = _apply_stat_updates(char_stats, world_stats_dict, updates)

                msg_id = snowflake_svc.generate_id()
                asst_msg = ChatMessage(
                    id=msg_id,
                    session_id=session_id,
                    role="assistant",
                    content=full_content,
                    turn_number=turn,
                    is_active_variant=True,
                    created_at=_now(),
                )
                await chats_db.create_message(asst_msg)

                # Update snapshot for this turn
                snap = await chats_db.get_snapshot_at_turn(session_id, turn)
                if snap:
                    snap.character_stats = chats_db.serialize_stats(new_char)
                    snap.world_stats = chats_db.serialize_stats(new_world)
                    await chats_db.update_snapshot(snap)
                else:
                    snap_id = snowflake_svc.generate_id()
                    new_snap = ChatStateSnapshot(
                        id=snap_id,
                        session_id=session_id,
                        turn_number=turn,
                        location_id=chat.current_location_id,
                        character_stats=chats_db.serialize_stats(new_char),
                        world_stats=chats_db.serialize_stats(new_world),
                        created_at=_now(),
                    )
                    await chats_db.create_snapshot(new_snap)

                chat.character_stats = chats_db.serialize_stats(new_char)
                chat.world_stats = chats_db.serialize_stats(new_world)
                chat.modified_at = _now()
                await chats_db.update_session(chat)

                if updates:
                    await queue.put(_sse("stat_update", {"stats": {**new_char, **new_world}}))

                display_content = re.sub(
                    r"\[STAT_UPDATE\].*?\[/STAT_UPDATE\]", "", full_content, flags=re.DOTALL
                ).strip()
                msg_resp = ChatMessageResponse(
                    id=str(asst_msg.id),
                    role="assistant",
                    content=display_content,
                    turn_number=turn,
                    tool_calls=None,
                    is_active_variant=True,
                    created_at=asst_msg.created_at.isoformat(),
                )
                await queue.put(_sse("done", {"message": msg_resp.model_dump()}))
            except Exception as exc:
                logger.exception("Regeneration error")
                await queue.put(_sse("error", {"detail": str(exc)}))
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_llm())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            if not task.done():
                task.cancel()

    return _stream()
