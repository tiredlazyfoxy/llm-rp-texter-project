"""Chain generation service — planning → writing pipeline.

PURPOSE
    Implements the 'chain' generation mode: planning stage (LLM with tools
    produces structured JSON GenerationPlanOutput) followed by writing stage
    (LLM produces narrative prose based on the plan).

USAGE
    Called by chat_agent_service dispatcher when world.generation_mode == "chain".

CHANGELOG
    stage3_step2b — Created
"""

import asyncio
import functools
import json
import logging
import re
from collections.abc import AsyncGenerator, Callable
from typing import Any

from fastapi import HTTPException, status

from app.db import chats as chats_db
from app.db import worlds as worlds_db
from app.models.chat_message import ChatMessage
from app.models.chat_state_snapshot import ChatStateSnapshot
from app.models.schemas.pipeline import GenerationPlanOutput, PipelineConfig
from app.services import snowflake as snowflake_svc
from app.services.chat_agent_service import (
    build_llm_messages,
    build_message_response,
    create_thinking_callback,
    now,
    sse,
)
from app.services.chat_context import build_chat_context
from app.services.chat_tools import get_chat_tools, get_writer_tools
from app.services.llm_chat import get_llm_client_for_model
from app.services.prompts.planning_system_prompt import build_planning_system_prompt
from app.services.prompts.writing_plan_message import build_writing_plan_message
from app.services.prompts.writing_system_prompt import build_writing_system_prompt
from app.services.stat_validation import validate_and_apply_stat_updates

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_updated_stats(
    char_stats: dict[str, Any],
    world_stats: dict[str, Any],
) -> str:
    """Format post-update stats for the writing plan message."""
    parts: list[str] = []
    if char_stats:
        parts.append("Character stats:")
        for name, value in char_stats.items():
            parts.append(f"  {name}: {value}")
    if world_stats:
        parts.append("World stats:")
        for name, value in world_stats.items():
            parts.append(f"  {name}: {value}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Tool wrapping with visibility filtering
# ---------------------------------------------------------------------------

def _make_tool_wrapper(
    name: str,
    fn: Callable,
    queue: asyncio.Queue,
    tool_call_records: list[dict[str, Any]],
    caller_role: str,
) -> Callable:
    """Wrap tool callable for SSE emission with visibility filtering."""
    @functools.wraps(fn)
    async def wrapper(**kwargs: Any) -> str:
        # Editor+ sees tool call details; players only get status
        if caller_role != "player":
            await queue.put(sse("tool_call_start", {"tool_name": name, "arguments": kwargs}))
        else:
            await queue.put(sse("status", {"text": f"Using {name}..."}))

        try:
            result = await fn(**kwargs)
        except Exception as exc:
            error_msg = f"Tool error: {exc}"
            if caller_role != "player":
                await queue.put(sse("tool_call_result", {"tool_name": name, "result": error_msg}))
            tool_call_records.append({
                "tool_name": name,
                "arguments": kwargs,
                "result": error_msg,
            })
            return error_msg

        if caller_role != "player":
            await queue.put(sse("tool_call_result", {"tool_name": name, "result": result}))
        tool_call_records.append({
            "tool_name": name,
            "arguments": kwargs,
            "result": result,
        })
        return result
    return wrapper


# ---------------------------------------------------------------------------
# Thinking callback with visibility filtering
# ---------------------------------------------------------------------------

def _create_filtered_thinking_callback(
    queue: asyncio.Queue,
    content_parts: list[str],
    caller_role: str,
) -> Callable:
    """Thinking callback that filters thinking events for non-editor users."""
    state = {"in_thinking": False}

    async def on_delta(delta: str) -> None:
        text = delta
        if not state["in_thinking"] and "<think>" in text:
            idx = text.index("<think>")
            before = text[:idx]
            after = text[idx + 7:]
            if before:
                content_parts.append(before)
            state["in_thinking"] = True
            if after and caller_role != "player":
                await queue.put(sse("thinking", {"content": after}))
            return
        if state["in_thinking"] and "</think>" in text:
            idx = text.index("</think>")
            before = text[:idx]
            after = text[idx + 8:]
            if before and caller_role != "player":
                await queue.put(sse("thinking", {"content": before}))
            if caller_role != "player":
                await queue.put(sse("thinking_done", {}))
            state["in_thinking"] = False
            if after:
                content_parts.append(after)
            return
        if state["in_thinking"]:
            if caller_role != "player":
                await queue.put(sse("thinking", {"content": text}))
        else:
            content_parts.append(text)

    return on_delta


# ---------------------------------------------------------------------------
# JSON parsing with fallback
# ---------------------------------------------------------------------------

def _parse_plan_json(raw: str) -> GenerationPlanOutput | None:
    """Parse GenerationPlanOutput from LLM response with regex fallback."""
    # Strip thinking tags if present
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # Try direct parse
    try:
        data = json.loads(cleaned)
        return GenerationPlanOutput.model_validate(data)
    except Exception:
        pass

    # Fallback: extract JSON object via regex
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            data = json.loads(match.group(0))
            return GenerationPlanOutput.model_validate(data)
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# Core chain generation
# ---------------------------------------------------------------------------

async def _run_chain_generation(
    chat,  # ChatSession
    turn: int,
    session_id: int,
    llm_messages: list[dict[str, str]],
    queue: asyncio.Queue,
    caller_role: str,
    is_regenerate: bool = False,
) -> None:
    """Run the two-stage chain pipeline: planning → writing."""
    try:
        # Load world and parse pipeline config
        world = await worlds_db.get_by_id(chat.world_id)
        if world is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")

        try:
            pipeline = PipelineConfig.model_validate_json(world.pipeline)
        except Exception:
            pipeline = PipelineConfig(stages=[])

        if not pipeline.stages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chain mode requires at least one pipeline stage",
            )

        # Build context (shared by both stages)
        context = await build_chat_context(chat)

        # Find stages
        planning_stage = next(
            (s for s in pipeline.stages if s.step_type == "planning"), None,
        )
        writing_stage = next(
            (s for s in pipeline.stages if s.step_type == "writing"), None,
        )

        # ---------------------------------------------------------------
        # PLANNING STAGE
        # ---------------------------------------------------------------
        plan: GenerationPlanOutput | None = None
        tool_call_records: list[dict[str, Any]] = []

        if planning_stage:
            await queue.put(sse("phase", {"phase": "planning"}))
            await queue.put(sse("status", {"text": "Gathering context..."}))

            # Build planning prompt
            planning_prompt = build_planning_system_prompt(
                world_name=world.name,
                world_description=world.description,
                location_name=context["location_name"],
                location_description=context["location_description"],
                location_exits=context["location_exits"],
                present_npcs=context["present_npcs"],
                rules=context["rules"],
                stat_definitions=context["stat_definitions"],
                current_stats=context["current_stats"],
                character_name=chat.character_name,
                character_description=chat.character_description,
                user_instructions=chat.user_instructions,
                lore_parts=context["injected_lore"],
                admin_prompt=planning_stage.prompt,
            )

            # Resolve planning model
            planning_model_id = chat.tool_model_id or chat.text_model_id
            if not planning_model_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No model configured for planning stage",
                )

            # Get tools and wrap with visibility filtering
            tool_defs, tool_callables = get_chat_tools(chat.world_id, chat.id)
            wrapped_tools: dict[str, Callable] = {
                name: _make_tool_wrapper(name, fn, queue, tool_call_records, caller_role)
                for name, fn in tool_callables.items()
            }

            # Planning stage streaming — collect raw content
            planning_parts: list[str] = []
            planning_callback = _create_filtered_thinking_callback(
                queue, planning_parts, caller_role,
            )

            # LLM options
            options: dict = {
                "temperature": chat.tool_temperature,
                "top_p": chat.tool_top_p,
                "repeat_penalty": chat.tool_repeat_penalty,
            }

            max_loops = planning_stage.max_agent_steps or 10

            client = await get_llm_client_for_model(planning_model_id)
            async with client:
                await client.chat_with_tools(
                    llm_messages,
                    tools_definitions=tool_defs,
                    tools=wrapped_tools,
                    system=planning_prompt,
                    options=options,
                    max_loops=max_loops,
                    stream=True,
                    on_delta=planning_callback,
                )

            planning_raw = "".join(planning_parts)

            # Parse plan JSON
            await queue.put(sse("status", {"text": "Planning response..."}))
            plan = _parse_plan_json(planning_raw)
            if plan is None:
                logger.error("Failed to parse planning JSON: %s", planning_raw[:500])
                await queue.put(sse("error", {"detail": "Planning stage produced invalid JSON"}))
                return

        # If no planning stage, create empty plan
        if plan is None:
            plan = GenerationPlanOutput()

        # Validate and apply stat updates from plan
        char_stats = chats_db.parse_stats(chat.character_stats)
        world_stats = chats_db.parse_stats(chat.world_stats)

        if plan.stat_updates:
            updates_dict = {su.name: su.value for su in plan.stat_updates}
            new_char, new_world = validate_and_apply_stat_updates(
                updates_dict, context["stat_defs_list"], char_stats, world_stats,
            )
        else:
            new_char, new_world = char_stats, world_stats

        # Emit stat_update (always — marks phase boundary)
        await queue.put(sse("stat_update", {"stats": {**new_char, **new_world}}))

        # ---------------------------------------------------------------
        # WRITING STAGE
        # ---------------------------------------------------------------
        prose_content = ""

        if writing_stage:
            await queue.put(sse("phase", {"phase": "writing"}))
            await queue.put(sse("status", {"text": "Writing..."}))

            # Build writing prompt
            writing_prompt = build_writing_system_prompt(
                world_name=world.name,
                world_description=world.description,
                character_name=chat.character_name,
                character_description=chat.character_description,
                lore_parts=context["injected_lore"],
                admin_prompt=writing_stage.prompt,
                user_instructions=chat.user_instructions,
            )

            # Build writer messages: summaries + clean user/assistant messages + plan
            writer_messages: list[dict[str, str]] = []

            summaries = await chats_db.list_summaries(session_id)
            for s in summaries:
                writer_messages.append({
                    "role": "user",
                    "content": f"[Summary of turns {s.start_turn}\u2013{s.end_turn}]:\n{s.content}",
                })

            # Clean messages: user + assistant only (no tool_calls content)
            all_active = await chats_db.list_active_messages(session_id)
            for m in all_active:
                if m.role in ("user", "assistant"):
                    writer_messages.append({
                        "role": m.role,
                        "content": m.content,
                    })
                elif m.role == "system":
                    writer_messages.append({
                        "role": "user",
                        "content": m.content,
                    })

            # Reload context in case move_to_location was called during planning
            chat_refreshed = await chats_db.get_session_by_id(session_id)
            if chat_refreshed:
                writer_context = await build_chat_context(chat_refreshed)
            else:
                writer_context = context

            # Format post-update stats for the writer
            updated_stats = _format_updated_stats(new_char, new_world)

            # Add plan message with structural scene context
            plan_message = build_writing_plan_message(
                collected_data=plan.collected_data,
                decisions=plan.decisions,
                location_name=writer_context["location_name"],
                present_npcs=writer_context["present_npcs"],
                current_stats=updated_stats,
            )
            writer_messages.append({"role": "user", "content": plan_message})

            # Resolve writing model
            writing_model_id = chat.text_model_id
            if not writing_model_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No model configured for writing stage",
                )

            # Get read-only tools for the writer
            writer_tool_defs, writer_tool_callables = get_writer_tools(
                chat.world_id, chat.id,
            )
            writer_tool_records: list[dict[str, Any]] = []
            wrapped_writer_tools: dict[str, Callable] = {
                name: _make_tool_wrapper(name, fn, queue, writer_tool_records, caller_role)
                for name, fn in writer_tool_callables.items()
            }

            # Writing stage streaming with thinking tag detection
            writing_parts: list[str] = []
            writing_callback = create_thinking_callback(queue, writing_parts)

            writing_options: dict = {
                "temperature": chat.text_temperature,
                "top_p": chat.text_top_p,
                "repeat_penalty": chat.text_repeat_penalty,
            }

            writer_client = await get_llm_client_for_model(writing_model_id)
            async with writer_client:
                await writer_client.chat_with_tools(
                    writer_messages,
                    tools_definitions=writer_tool_defs,
                    tools=wrapped_writer_tools,
                    system=writing_prompt,
                    options=writing_options,
                    max_loops=5,
                    stream=True,
                    on_delta=writing_callback,
                )

            prose_content = "".join(writing_parts)

            # Merge writer tool records into main records
            tool_call_records.extend(writer_tool_records)

        # ---------------------------------------------------------------
        # FINALIZE
        # ---------------------------------------------------------------

        # Save assistant message
        msg_id = snowflake_svc.generate_id()
        msg_now = now()
        plan_json = plan.model_dump_json() if plan else None
        asst_msg = ChatMessage(
            id=msg_id,
            session_id=session_id,
            role="assistant",
            content=prose_content,
            turn_number=turn,
            tool_calls=json.dumps(tool_call_records) if tool_call_records else None,
            generation_plan=plan_json,
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
                snap.location_id = chat.current_location_id
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

        # Emit done
        msg_resp = build_message_response(
            msg_id=msg_id,
            content=prose_content,
            turn_number=turn,
            created_at=msg_now,
            tool_calls=tool_call_records if tool_call_records else None,
            generation_plan=plan_json,
        )
        await queue.put(sse("done", {"message": msg_resp}))

    except Exception as exc:
        logger.exception("Chain generation error")
        await queue.put(sse("error", {"detail": str(exc)}))
    finally:
        await queue.put(None)


# ---------------------------------------------------------------------------
# generate_chain_response
# ---------------------------------------------------------------------------

def generate_chain_response(
    session_id: int,
    user_id: int,
    user_message: str,
    caller_role: str,
) -> AsyncGenerator[str, None]:
    """Chain mode generation: planning → writing pipeline."""

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

        # Build LLM message history
        llm_messages = await build_llm_messages(session_id)

        # Run chain generation
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        task = asyncio.create_task(
            _run_chain_generation(
                chat, turn, session_id, llm_messages, queue, caller_role,
            )
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
# regenerate_chain_response
# ---------------------------------------------------------------------------

def regenerate_chain_response(
    session_id: int,
    user_id: int,
    caller_role: str,
) -> AsyncGenerator[str, None]:
    """Chain mode regeneration: mark old inactive, restore stats, re-run pipeline."""

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
        if user_content:
            llm_messages.append({"role": "user", "content": user_content})

        # Run chain generation
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        task = asyncio.create_task(
            _run_chain_generation(
                chat, turn, session_id, llm_messages, queue, caller_role,
                is_regenerate=True,
            )
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
