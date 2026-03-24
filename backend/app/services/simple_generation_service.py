"""Simple generation service — single LLM call with tools.

PURPOSE
    Implements the 'simple' generation mode: builds rich context, gets tools,
    calls chat_with_tools with streaming, validates stat updates.

USAGE
    Called by chat_agent_service dispatcher when world.generation_mode == "simple".

CHANGELOG
    stage3_step2a — Created
"""

import asyncio
import functools
import json
import logging
from collections.abc import AsyncGenerator, Callable
from typing import Any

from fastapi import HTTPException, status

from app.db import chats as chats_db
from app.models.chat_message import ChatMessage
from app.models.chat_state_snapshot import ChatStateSnapshot
from app.services import snowflake as snowflake_svc
from app.services.chat_agent_service import (
    build_llm_messages,
    build_message_response,
    create_thinking_callback,
    now,
    parse_stat_updates,
    sse,
    strip_stat_block,
)
from app.services.chat_context import build_chat_context
from app.services.chat_tools import get_chat_tools
from app.services.llm_chat import get_llm_client_for_model
from app.services.prompts.chat_system_prompt import build_rich_chat_system_prompt
from app.services.stat_validation import validate_and_apply_stat_updates

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool wrapping for SSE emission
# ---------------------------------------------------------------------------

def _make_tool_wrapper(
    name: str,
    fn: Callable,
    queue: asyncio.Queue,
    tool_call_records: list[dict[str, Any]],
) -> Callable:
    """Wrap a tool callable to emit SSE events and record calls."""
    @functools.wraps(fn)
    async def wrapper(**kwargs: Any) -> str:
        await queue.put(sse("tool_call_start", {"tool_name": name, "arguments": kwargs}))
        try:
            result = await fn(**kwargs)
        except Exception as exc:
            error_msg = f"Tool error: {exc}"
            await queue.put(sse("tool_call_result", {"tool_name": name, "result": error_msg}))
            tool_call_records.append({
                "tool_name": name,
                "arguments": kwargs,
                "result": error_msg,
            })
            return error_msg
        await queue.put(sse("tool_call_result", {"tool_name": name, "result": result}))
        tool_call_records.append({
            "tool_name": name,
            "arguments": kwargs,
            "result": result,
        })
        return result
    return wrapper


# ---------------------------------------------------------------------------
# Core generation logic (shared by generate and regenerate)
# ---------------------------------------------------------------------------

async def _run_generation(
    chat,  # ChatSession
    turn: int,
    session_id: int,
    llm_messages: list[dict[str, str]],
    queue: asyncio.Queue,
    is_regenerate: bool = False,
) -> None:
    """Run the LLM generation with tools, stat validation, and persistence."""
    try:
        # Resolve model: prefer tool_model_id, fall back to text_model_id
        model_id = chat.tool_model_id or chat.text_model_id
        if not model_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No model configured",
            )

        # Build context
        context = await build_chat_context(chat)

        # Build rich system prompt
        system_prompt = build_rich_chat_system_prompt(
            world_name=context["world"].name,
            world_description=context["world"].description,
            admin_system_prompt=context["world"].system_prompt,
            location_name=context["location_name"],
            location_description=context["location_description"],
            location_exits=context["location_exits"],
            present_npcs=context["present_npcs"],
            rules=context["rules"],
            stat_definitions=context["stat_definitions"],
            current_stats=context["current_stats"],
            character_name=chat.character_name,
            character_description=chat.character_description,
            injected_lore=context["injected_lore"],
            user_instructions=chat.user_instructions,
            memories=context["memories"],
        )

        # Get tools
        tool_defs, tool_callables = get_chat_tools(chat.world_id, chat.id)

        # Wrap tools with SSE emission + recording
        tool_call_records: list[dict[str, Any]] = []
        wrapped_tools: dict[str, Callable] = {
            name: _make_tool_wrapper(name, fn, queue, tool_call_records)
            for name, fn in tool_callables.items()
        }

        # Prepare streaming
        content_parts: list[str] = []
        thinking_parts: list[str] = []
        on_delta = create_thinking_callback(queue, content_parts, thinking_parts)

        # LLM options — strip enable_thinking (not supported by chat_with_tools)
        options: dict = {
            "temperature": chat.tool_temperature if chat.tool_model_id else chat.text_temperature,
            "top_p": chat.tool_top_p if chat.tool_model_id else chat.text_top_p,
            "repeat_penalty": chat.tool_repeat_penalty if chat.tool_model_id else chat.text_repeat_penalty,
        }

        # Call LLM with tools
        client = await get_llm_client_for_model(model_id)
        async with client:
            await client.chat_with_tools(
                llm_messages,
                tools_definitions=tool_defs,
                tools=wrapped_tools,
                system=system_prompt,
                options=options,
                max_loops=15,
                stream=True,
                on_delta=on_delta,
            )

        full_content = "".join(content_parts)

        # Parse and validate stat updates
        updates = parse_stat_updates(full_content)
        char_stats = chats_db.parse_stats(chat.character_stats)
        world_stats = chats_db.parse_stats(chat.world_stats)
        new_char, new_world = validate_and_apply_stat_updates(
            updates, context["stat_defs_list"], char_stats, world_stats,
        )

        # Save assistant message
        msg_id = snowflake_svc.generate_id()
        msg_now = now()
        thinking_text = "".join(thinking_parts) if thinking_parts else None
        asst_msg = ChatMessage(
            id=msg_id,
            session_id=session_id,
            role="assistant",
            content=full_content,
            turn_number=turn,
            tool_calls=json.dumps(tool_call_records) if tool_call_records else None,
            thinking_content=thinking_text,
            is_active_variant=True,
            created_at=msg_now,
        )
        await chats_db.create_message(asst_msg)

        # Update session state
        chat.current_turn = turn
        chat.character_stats = chats_db.serialize_stats(new_char)
        chat.world_stats = chats_db.serialize_stats(new_world)
        chat.modified_at = now()
        await chats_db.update_session(chat)

        # Save/update snapshot
        if is_regenerate:
            snap = await chats_db.get_snapshot_at_turn(session_id, turn)
            if snap:
                snap.character_stats = chats_db.serialize_stats(new_char)
                snap.world_stats = chats_db.serialize_stats(new_world)
                await chats_db.update_snapshot(snap)
            else:
                snap = ChatStateSnapshot(
                    id=snowflake_svc.generate_id(),
                    session_id=session_id,
                    turn_number=turn,
                    location_id=chat.current_location_id,
                    character_stats=chats_db.serialize_stats(new_char),
                    world_stats=chats_db.serialize_stats(new_world),
                    created_at=now(),
                )
                await chats_db.create_snapshot(snap)
        else:
            snap = ChatStateSnapshot(
                id=snowflake_svc.generate_id(),
                session_id=session_id,
                turn_number=turn,
                location_id=chat.current_location_id,
                character_stats=chats_db.serialize_stats(new_char),
                world_stats=chats_db.serialize_stats(new_world),
                created_at=now(),
            )
            await chats_db.create_snapshot(snap)

        # Emit stat update event
        if updates:
            await queue.put(sse("stat_update", {"stats": {**new_char, **new_world}}))

        # Build done event
        display_content = strip_stat_block(full_content)
        msg_resp = build_message_response(
            msg_id=msg_id,
            content=display_content,
            turn_number=turn,
            created_at=msg_now,
            tool_calls=tool_call_records if tool_call_records else None,
            thinking_content=thinking_text,
        )
        await queue.put(sse("done", {"message": msg_resp}))

    except Exception as exc:
        logger.exception("Simple generation error")
        await queue.put(sse("error", {"detail": str(exc)}))
    finally:
        await queue.put(None)


# ---------------------------------------------------------------------------
# generate_simple_response
# ---------------------------------------------------------------------------

def generate_simple_response(
    session_id: int,
    user_id: int,
    user_message: str,
) -> AsyncGenerator[str, None]:
    """Simple mode generation: single LLM call with tools and rich context."""

    async def _stream() -> AsyncGenerator[str, None]:
        chat = await chats_db.get_session_by_id(session_id)
        if chat is None or chat.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        if chat.status != "active":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chat is not active")

        turn = chat.current_turn + 1

        # Save user message
        user_msg = ChatMessage(
            id=snowflake_svc.generate_id(),
            session_id=session_id,
            role="user",
            content=user_message,
            turn_number=turn,
            is_active_variant=True,
            created_at=now(),
        )
        await chats_db.create_message(user_msg)

        # Acknowledge user message to frontend
        yield sse("user_ack", {
            "id": str(user_msg.id),
            "turn_number": user_msg.turn_number,
            "created_at": user_msg.created_at.isoformat(),
        })

        # Build LLM message history
        llm_messages = await build_llm_messages(session_id)

        # Run generation in background task with queue
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        task = asyncio.create_task(
            _run_generation(chat, turn, session_id, llm_messages, queue)
        )

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
# regenerate_simple_response
# ---------------------------------------------------------------------------

def regenerate_simple_response(
    session_id: int,
    user_id: int,
) -> AsyncGenerator[str, None]:
    """Simple mode regeneration: mark old inactive, restore stats, re-run."""

    async def _stream() -> AsyncGenerator[str, None]:
        chat = await chats_db.get_session_by_id(session_id)
        if chat is None or chat.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        if chat.status != "active" or chat.current_turn == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot regenerate")

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

        # Build message history excluding current turn's assistant
        llm_messages: list[dict[str, str]] = []
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

        # Run generation
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        task = asyncio.create_task(
            _run_generation(chat, turn, session_id, llm_messages, queue, is_regenerate=True)
        )

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
