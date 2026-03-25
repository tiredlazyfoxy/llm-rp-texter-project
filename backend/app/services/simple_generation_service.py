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
from app.db import locations as locations_db
from app.models.chat_message import ChatMessage
from app.models.chat_state_snapshot import ChatStateSnapshot
from app.services import snowflake as snowflake_svc
from app.services.chat_agent_service import (
    _lp,
    build_llm_messages,
    build_message_response,
    create_thinking_callback,
    now,
    parse_stat_updates,
    sse,
    strip_stat_block,
)
from app.services.chat_context import build_chat_context
from app.services.chat_tools import get_chat_tools, get_tools_by_names
from app.services.llm_chat import get_llm_client_for_model
from app.services.prompts.chat_system_prompt import build_rich_chat_system_prompt
from app.services.prompts.prompt_injection import (
    build_tools_description,
    resolve_prompt_template,
)
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
    stage_name: str = "Generation",
) -> Callable:
    """Wrap a tool callable to emit SSE events and record calls."""
    @functools.wraps(fn)
    async def wrapper(**kwargs: Any) -> str:
        logger.debug("Tool call: %s(%s)", name, ", ".join(f"{k}={v!r}" for k, v in kwargs.items()))
        await queue.put(sse("tool_call_start", {
            "tool_name": name, "arguments": kwargs, "stage_name": stage_name,
        }))
        try:
            result = await fn(**kwargs)
        except Exception as exc:
            error_msg = f"Tool error: {exc}"
            logger.debug("Tool error: %s -> %s", name, error_msg[:200])
            await queue.put(sse("tool_call_result", {"tool_name": name, "result": error_msg}))
            tool_call_records.append({
                "tool_name": name, "arguments": kwargs,
                "result": error_msg, "stage_name": stage_name,
            })
            return error_msg
        logger.debug("Tool result: %s -> %s", name, result[:200] if isinstance(result, str) else str(result)[:200])
        await queue.put(sse("tool_call_result", {"tool_name": name, "result": result}))
        tool_call_records.append({
            "tool_name": name, "arguments": kwargs,
            "result": result, "stage_name": stage_name,
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
        lp = _lp(session_id, turn)

        # Resolve model: prefer tool_model_id, fall back to text_model_id
        model_id = chat.tool_model_id or chat.text_model_id
        if not model_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No model configured",
            )
        logger.debug("%s Model resolved: %s", lp, model_id)

        # Build context
        context = await build_chat_context(chat)
        logger.debug(
            "%s Context: location=%s, npcs=%d chars, rules=%d chars, stats=%d chars",
            lp, context["location_name"] or "(none)",
            len(context["present_npcs"]), len(context["rules"]), len(context["current_stats"]),
        )

        # Parse tool selection from world config
        world = context["world"]
        try:
            configured_tools: list[str] = json.loads(world.simple_tools) if world.simple_tools else []
        except (json.JSONDecodeError, TypeError):
            configured_tools = []

        # Get tools (filtered or all chat tools as fallback)
        if configured_tools:
            tool_defs, tool_callables = get_tools_by_names(
                configured_tools, chat.world_id, chat.id,
            )
        else:
            tool_defs, tool_callables = get_chat_tools(chat.world_id, chat.id)
        logger.debug("%s Tools: %s", lp, list(tool_callables.keys()))

        # Build system prompt (template resolution or legacy fallback)
        if world.system_prompt and world.system_prompt.strip():
            tools_desc = build_tools_description(
                [d["function"]["name"] for d in tool_defs],
            )
            system_prompt = resolve_prompt_template(
                world.system_prompt,
                WORLD_NAME=world.name,
                RULES=context["rules"],
                INJECTED_LORE=context["injected_lore"],
                LOCATION=context["location_block"],
                CHARACTER_NAME=chat.character_name,
                CHARACTER_STATS=context["character_stats"],
                WORLD_STATS=context["world_stats"],
                USER_INSTRUCTIONS=chat.user_instructions or "",
                TURN_FACTS="",
                TURN_DECISIONS="",
                TOOLS=tools_desc,
            )
        else:
            system_prompt = build_rich_chat_system_prompt(
                world_name=world.name,
                world_description=world.description,
                admin_system_prompt=world.system_prompt,
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
        logger.debug("%s System prompt: %d chars", lp, len(system_prompt))

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
        logger.debug(
            "%s Calling chat_with_tools: model=%s, messages=%d, tools=%d, max_loops=15, options=%s",
            lp, model_id, len(llm_messages), len(tool_defs), options,
        )
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
        logger.debug(
            "%s LLM completed: content=%d chars, thinking=%d chars, tool_calls=%d",
            lp, len(full_content), len("".join(thinking_parts)), len(tool_call_records),
        )

        # Parse and validate stat updates
        updates = parse_stat_updates(full_content)
        logger.debug("%s Stat updates parsed: %s", lp, updates if updates else "(none)")
        char_stats = chats_db.parse_stats(chat.character_stats)
        world_stats = chats_db.parse_stats(chat.world_stats)
        new_char, new_world = validate_and_apply_stat_updates(
            updates, context["stat_defs_list"], char_stats, world_stats,
        )
        logger.debug("%s Stats after validation: char=%s, world=%s", lp, new_char, new_world)

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
        logger.debug("%s Assistant message saved: id=%d, content=%d chars", lp, msg_id, len(full_content))

        # Update session state
        chat.current_turn = turn
        chat.character_stats = chats_db.serialize_stats(new_char)
        chat.world_stats = chats_db.serialize_stats(new_world)
        chat.modified_at = now()
        await chats_db.update_session(chat)
        logger.debug("%s Session updated: turn=%d", lp, turn)

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
    variant_index: int | None = None,
) -> AsyncGenerator[str, None]:
    """Simple mode generation: single LLM call with tools and rich context."""

    async def _stream() -> AsyncGenerator[str, None]:
        chat = await chats_db.get_session_by_id(session_id)
        if chat is None or chat.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        if chat.status != "active":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chat is not active")

        turn = chat.current_turn + 1
        logger.debug("[s:%d] Starting simple generation, current_turn=%d", session_id, chat.current_turn)

        # Handle variant selection + clear variants atomically
        from app.services.chat_service import _load_variants, _save_variants
        variants = _load_variants(chat)
        if variant_index is not None and 0 <= variant_index < len(variants):
            from app.services.chat_service import continue_chat
            await continue_chat(session_id, chat.user_id, variant_index)
            chat = await chats_db.get_session_by_id(session_id)
        elif variants:
            _save_variants(chat, [])
            await chats_db.update_session(chat)

        # Reuse existing user message at this turn (e.g. after edit) or create new
        existing = await chats_db.get_user_message_at_turn(session_id, turn)
        if existing and existing.content == user_message:
            user_msg = existing
        else:
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
        logger.debug("[s:%d] Starting simple regeneration, turn=%d", session_id, turn)

        # Capture current stats/location before reset (for variant storage)
        old_char_stats = chats_db.parse_stats(chat.character_stats)
        old_world_stats = chats_db.parse_stats(chat.world_stats)
        old_location_id = str(chat.current_location_id) if chat.current_location_id else None
        old_location_name: str | None = None
        if chat.current_location_id:
            loc = await locations_db.get_by_id(chat.current_location_id)
            old_location_name = loc.name if loc else None

        # Move current assistant message to generation_variants
        from app.services.chat_service import _msg_to_variant, _load_variants, _save_variants
        current_asst = await chats_db.get_active_assistant_at_turn(session_id, turn)
        if current_asst:
            variants = _load_variants(chat)
            variants.append(_msg_to_variant(
                current_asst,
                character_stats=old_char_stats,
                world_stats=old_world_stats,
                location_id=old_location_id,
                location_name=old_location_name,
            ))
            _save_variants(chat, variants)
            await chats_db.delete_message_by_id(current_asst.id)

        # Reload user message for this turn
        user_msg = await chats_db.get_user_message_at_turn(session_id, turn)
        user_content = user_msg.content if user_msg else ""

        # Restore stats and location from previous snapshot
        prev_snap = await chats_db.get_snapshot_at_turn(session_id, turn - 1)
        if prev_snap:
            chat.character_stats = prev_snap.character_stats
            chat.world_stats = prev_snap.world_stats
            chat.current_location_id = prev_snap.location_id
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
