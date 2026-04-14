"""Chain generation service — planning → writing pipeline.

PURPOSE
    Implements the 'chain' generation mode: planning stage (LLM with planning
    tools builds PlanningContext) followed by writing stage (LLM produces
    narrative prose based on the plan).

USAGE
    Called by chat_agent_service dispatcher when world.generation_mode == "chain".

CHANGELOG
    stage3_step2b — Created
    stage4_step4 — Replaced JSON parsing with tool-based PlanningContext
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
from app.db import worlds as worlds_db
from app.models.chat_message import ChatMessage
from app.models.chat_state_snapshot import ChatStateSnapshot
from app.models.schemas.pipeline import GenerationPlanOutput, PipelineConfig, PlanningContext
from app.services import snowflake as snowflake_svc
from app.services.chat_agent_service import (
    _lp,
    build_llm_messages,
    build_message_response,
    create_thinking_callback,
    now,
    sse,
)
from app.services.chat_context import ChatContext, build_chat_context
from app.services.chat_tools import DecisionState, ToolContext, build_tools
from app.services.llm_chat import get_llm_client_for_model
from app.services.prompts.planning_system_prompt import build_planning_system_prompt
from app.services.prompts.prompt_injection import (
    build_tools_description,
    format_decisions,
    format_facts,
    resolve_prompt_template,
)
from app.services.chat_tools import TOOL_REGISTRY
from app.services.prompts.tool_catalog import ALL_TOOL_NAMES
from app.services.prompts.writing_plan_message import build_writing_plan_message
from app.services.prompts.writing_system_prompt import build_writing_system_prompt

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
    stage_name: str = "",
) -> Callable:
    """Wrap tool callable for SSE emission with visibility filtering."""
    @functools.wraps(fn)
    async def wrapper(**kwargs: Any) -> str:
        logger.debug("Tool call: %s(%s)", name, ", ".join(f"{k}={v!r}" for k, v in kwargs.items()))
        # Editor+ sees tool call details; players only get status
        if caller_role != "player":
            await queue.put(sse("tool_call_start", {
                "tool_name": name, "arguments": kwargs, "stage_name": stage_name,
            }))
        else:
            await queue.put(sse("status", {"text": f"Using {name}..."}))

        try:
            result = await fn(**kwargs)
        except Exception as exc:
            error_msg = f"Tool error: {exc}"
            logger.debug("Tool error: %s -> %s", name, error_msg[:200])
            if caller_role != "player":
                await queue.put(sse("tool_call_result", {"tool_name": name, "result": error_msg}))
            tool_call_records.append({
                "tool_name": name, "arguments": kwargs,
                "result": error_msg, "stage_name": stage_name,
            })
            return error_msg

        logger.debug("Tool result: %s -> %s", name, result[:200] if isinstance(result, str) else str(result)[:200])
        if caller_role != "player":
            await queue.put(sse("tool_call_result", {"tool_name": name, "result": result}))
        tool_call_records.append({
            "tool_name": name, "arguments": kwargs,
            "result": result, "stage_name": stage_name,
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
    thinking_parts: list[str] | None = None,
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
            if after:
                if thinking_parts is not None:
                    thinking_parts.append(after)
                if caller_role != "player":
                    await queue.put(sse("thinking", {"content": after}))
            return
        if state["in_thinking"] and "</think>" in text:
            idx = text.index("</think>")
            before = text[:idx]
            after = text[idx + 8:]
            if before:
                if thinking_parts is not None:
                    thinking_parts.append(before)
                if caller_role != "player":
                    await queue.put(sse("thinking", {"content": before}))
            if caller_role != "player":
                await queue.put(sse("thinking_done", {}))
            state["in_thinking"] = False
            if after:
                content_parts.append(after)
            return
        if state["in_thinking"]:
            if thinking_parts is not None:
                thinking_parts.append(text)
            if caller_role != "player":
                await queue.put(sse("thinking", {"content": text}))
        else:
            content_parts.append(text)

    return on_delta


# ---------------------------------------------------------------------------
# Prompt resolution helpers
# ---------------------------------------------------------------------------

def _build_placeholder_values(
    context: ChatContext, chat: Any, turn_facts: str, turn_decisions: str,
    tools_desc: str, decision: str = "",
) -> dict[str, str]:
    """Build the common placeholder kwargs for resolve_prompt_template."""
    return {
        "WORLD_NAME": context["world"].name,
        "RULES": context["rules"],
        "INJECTED_LORE": context["injected_lore"],
        "LOCATION": context["location_block"],
        "CHARACTER_NAME": chat.character_name,
        "CHARACTER_STATS": context["character_stats"],
        "WORLD_STATS": context["world_stats"],
        "USER_INSTRUCTIONS": chat.user_instructions or "",
        "TURN_FACTS": turn_facts,
        "TURN_DECISIONS": turn_decisions,
        "DECISION": decision,
        "TOOLS": tools_desc,
    }


def _resolve_tool_prompt(
    stage, context: ChatContext, chat: Any, turn_facts: str, turn_decisions: str,
    tools_desc: str, decision: str = "",
) -> str:
    """Resolve tool-step system prompt: template or legacy fallback."""
    if stage.prompt and stage.prompt.strip():
        values = _build_placeholder_values(context, chat, turn_facts, turn_decisions, tools_desc, decision)
        return resolve_prompt_template(stage.prompt, **values)
    return build_planning_system_prompt(
        world_name=context["world"].name,
        world_description=context["world"].description,
        location_name=context["location_name"],
        location_description=context["location_description"],
        location_exits=context["location_exits"],
        present_npcs=context["present_npcs"],
        rules=context["rules"],
        stat_definitions=context["stat_definitions"],
        current_stats=context["current_stats"],
        character_name=chat.character_name,
        character_description=chat.character_description,
        user_instructions=chat.user_instructions or "",
        lore_parts=context["injected_lore"],
        admin_prompt="",
    )


def _resolve_writer_prompt(
    stage, context: ChatContext, chat: Any, turn_facts: str, turn_decisions: str,
    decision: str = "",
) -> str:
    """Resolve writer-step system prompt: template or legacy fallback."""
    if stage.prompt and stage.prompt.strip():
        tools_desc = build_tools_description(stage.tools)
        values = _build_placeholder_values(context, chat, turn_facts, turn_decisions, tools_desc, decision)
        return resolve_prompt_template(stage.prompt, **values)
    return build_writing_system_prompt(
        world_name=context["world"].name,
        world_description=context["world"].description,
        character_name=chat.character_name,
        character_description=chat.character_description,
        lore_parts=context["injected_lore"],
        admin_prompt="",
        user_instructions=chat.user_instructions or "",
    )


def _combine_planning_contexts(contexts: list[PlanningContext]) -> GenerationPlanOutput:
    """Merge all PlanningContexts into a single GenerationPlanOutput."""
    return GenerationPlanOutput(
        collected_data="\n".join(f for ctx in contexts for f in ctx.facts),
        decisions=[d for ctx in contexts for d in ctx.decisions],
        stat_updates=[su for ctx in contexts for su in ctx.stat_updates],
    )


def _migrate_legacy_stages(pipeline: PipelineConfig) -> None:
    """On-read migration: 'planning' → 'tool', 'writing' → 'writer'.

    Legacy stages with no ``tools`` list get seeded with the full catalog so
    admins landing on the editor see something to work with. New-style stages
    always honor ``stage.tools`` verbatim.
    """
    for stage in pipeline.stages:
        if stage.step_type == "planning":
            stage.step_type = "tool"
            if not stage.tools:
                stage.tools = list(ALL_TOOL_NAMES)
        elif stage.step_type == "writing":
            stage.step_type = "writer"
            if not stage.tools:
                # Writer stage has no planning/director state — seed with the
                # subset of catalog tools whose requirements are satisfied by
                # (world_id, session_id) alone.
                available = {"world_id", "session_id"}
                stage.tools = [
                    n for n, spec in TOOL_REGISTRY.items()
                    if set(spec.requires) <= available
                ]


# ---------------------------------------------------------------------------
# Individual stage runners
# ---------------------------------------------------------------------------

async def _run_tool_stage(
    lp: str,
    stage,
    stage_idx: int,
    chat: Any,
    context: ChatContext,
    llm_messages: list[dict[str, str]],
    queue: asyncio.Queue,
    caller_role: str,
    all_planning_contexts: list[PlanningContext],
    char_stats: dict[str, Any],
    world_stats: dict[str, Any],
    tool_call_records: list[dict[str, Any]],
    decision_state: DecisionState,
    current_decision: str,
) -> str:
    """Execute a single tool step. Returns thinking text (may be empty)."""
    phase_label = stage.name or f"Tool step {stage_idx + 1}"
    logger.debug("%s === TOOL STAGE %d: %s ===", lp, stage_idx, phase_label)
    await queue.put(sse("phase", {"phase": "planning"}))
    await queue.put(sse("status", {"text": f"{phase_label}: Gathering context..."}))

    planning_ctx = PlanningContext()

    # Get tools — admin selection drives names; all required state is
    # available in this stage, so any catalog tool is fair game.
    tool_ctx = ToolContext(
        world_id=chat.world_id,
        session_id=chat.id,
        planning_context=planning_ctx,
        stat_defs=context["stat_defs_list"],
        char_stats=char_stats,
        world_stats=world_stats,
        decision_state=decision_state,
    )
    tool_defs, tool_callables = build_tools(stage.tools or [], tool_ctx)

    # Resolve prompt
    tools_desc = build_tools_description([d["function"]["name"] for d in tool_defs])
    prev_facts = format_facts(all_planning_contexts)
    prev_decisions = format_decisions(all_planning_contexts)
    system_prompt = _resolve_tool_prompt(
        stage, context, chat, prev_facts, prev_decisions, tools_desc, current_decision,
    )
    logger.debug("%s Tool prompt: %d chars", lp, len(system_prompt))

    # Model
    model_id = chat.tool_model_id or chat.text_model_id
    if not model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No model configured for tool stage {stage_idx}",
        )

    # Wrap tools, stream, call LLM
    stage_records: list[dict[str, Any]] = []
    wrapped = {
        name: _make_tool_wrapper(name, fn, queue, stage_records, caller_role, stage_name=phase_label)
        for name, fn in tool_callables.items()
    }
    planning_parts: list[str] = []
    stage_thinking: list[str] = []
    callback = _create_filtered_thinking_callback(queue, planning_parts, caller_role, stage_thinking)

    options = {
        "temperature": chat.tool_temperature,
        "top_p": chat.tool_top_p,
        "repeat_penalty": chat.tool_repeat_penalty,
    }
    max_loops = stage.max_agent_steps or 10

    logger.debug(
        "%s Tool stage: model=%s, messages=%d, tools=%d, max_loops=%d",
        lp, model_id, len(llm_messages), len(tool_defs), max_loops,
    )
    client = await get_llm_client_for_model(model_id)
    async with client:
        await client.chat_with_tools(
            llm_messages, tools_definitions=tool_defs, tools=wrapped,
            system=system_prompt, options=options, max_loops=max_loops,
            stream=True, on_delta=callback,
        )

    logger.debug(
        "%s Tool stage %d completed: facts=%d, decisions=%d, stat_updates=%d, tool_calls=%d",
        lp, stage_idx, len(planning_ctx.facts), len(planning_ctx.decisions),
        len(planning_ctx.stat_updates), len(stage_records),
    )

    all_planning_contexts.append(planning_ctx)
    tool_call_records.extend(stage_records)
    return "".join(stage_thinking)


async def _run_writer_stage(
    lp: str,
    stage,
    stage_idx: int,
    chat: Any,
    session_id: int,
    context: ChatContext,
    queue: asyncio.Queue,
    caller_role: str,
    all_planning_contexts: list[PlanningContext],
    char_stats: dict[str, Any],
    world_stats: dict[str, Any],
    tool_call_records: list[dict[str, Any]],
    current_decision: str,
) -> tuple[str, str]:
    """Execute a single writer step. Returns (prose_content, thinking_text)."""
    phase_label = stage.name or "Writing"
    logger.debug("%s === WRITER STAGE %d: %s ===", lp, stage_idx, phase_label)
    await queue.put(sse("phase", {"phase": "writing"}))
    await queue.put(sse("status", {"text": f"{phase_label}..."}))

    # Resolve prompt
    all_facts = format_facts(all_planning_contexts)
    all_decisions_str = format_decisions(all_planning_contexts)
    system_prompt = _resolve_writer_prompt(
        stage, context, chat, all_facts, all_decisions_str, current_decision,
    )

    # Build writer messages: summaries + clean history + plan
    writer_messages: list[dict[str, str]] = []
    summaries = await chats_db.list_summaries(session_id)
    for s in summaries:
        writer_messages.append({
            "role": "user",
            "content": f"[Summary of turns {s.start_turn}\u2013{s.end_turn}]:\n{s.content}",
        })
    all_active = await chats_db.list_active_messages(session_id)
    for m in all_active:
        if m.role in ("user", "assistant"):
            writer_messages.append({"role": m.role, "content": m.content})
        elif m.role == "system":
            writer_messages.append({"role": "user", "content": m.content})

    # Inject plan message
    combined_plan = _combine_planning_contexts(all_planning_contexts)
    updated_stats = _format_updated_stats(char_stats, world_stats)
    plan_message = build_writing_plan_message(
        collected_data=combined_plan.collected_data,
        decisions=combined_plan.decisions,
        location_name=context["location_name"],
        present_npcs=context["present_npcs"],
        current_stats=updated_stats,
    )
    writer_messages.append({"role": "user", "content": plan_message})
    logger.debug(
        "%s Writer prompt: %d chars, plan message: %d chars, messages: %d",
        lp, len(system_prompt), len(plan_message), len(writer_messages),
    )

    # Model
    model_id = chat.text_model_id
    if not model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No model configured for writer stage {stage_idx}",
        )

    # Get writer tools — admin selection drives names; writer has no
    # planning/director state, so only world/session-bound tools are valid.
    tool_ctx = ToolContext(world_id=chat.world_id, session_id=chat.id)
    tool_defs, tool_callables = build_tools(stage.tools or [], tool_ctx)

    stage_records: list[dict[str, Any]] = []
    wrapped = {
        name: _make_tool_wrapper(name, fn, queue, stage_records, caller_role, stage_name=phase_label)
        for name, fn in tool_callables.items()
    }

    # Stream
    writing_parts: list[str] = []
    writing_thinking: list[str] = []
    callback = create_thinking_callback(queue, writing_parts, writing_thinking)

    options = {
        "temperature": chat.text_temperature,
        "top_p": chat.text_top_p,
        "repeat_penalty": chat.text_repeat_penalty,
    }

    logger.debug(
        "%s Writer: model=%s, messages=%d, tools=%d, max_loops=20",
        lp, model_id, len(writer_messages), len(tool_defs),
    )
    client = await get_llm_client_for_model(model_id)
    async with client:
        await client.chat_with_tools(
            writer_messages, tools_definitions=tool_defs, tools=wrapped,
            system=system_prompt, options=options, max_loops=20,
            stream=True, on_delta=callback,
        )

    prose = "".join(writing_parts)
    logger.debug(
        "%s Writer completed: prose=%d chars, thinking=%d chars, writer_tool_calls=%d",
        lp, len(prose), len("".join(writing_thinking)), len(stage_records),
    )

    tool_call_records.extend(stage_records)
    return prose, "".join(writing_thinking)


async def _finalize_chain(
    lp: str,
    chat: Any,
    turn: int,
    session_id: int,
    queue: asyncio.Queue,
    prose_content: str,
    char_stats: dict[str, Any],
    world_stats: dict[str, Any],
    all_planning_contexts: list[PlanningContext],
    tool_call_records: list[dict[str, Any]],
    thinking_parts: list[dict[str, str]],
    is_regenerate: bool,
) -> None:
    """Save message, update session/snapshot, emit done."""
    new_char, new_world = char_stats, world_stats
    logger.debug("%s Stats after pipeline: char=%s, world=%s", lp, new_char, new_world)

    await queue.put(sse("stat_update", {"stats": {**new_char, **new_world}}))

    combined_plan = _combine_planning_contexts(all_planning_contexts)
    thinking_text = json.dumps(thinking_parts) if thinking_parts else None
    plan_json = combined_plan.model_dump_json() if all_planning_contexts else None

    # Save assistant message
    msg_id = snowflake_svc.generate_id()
    msg_now = now()
    asst_msg = ChatMessage(
        id=msg_id,
        session_id=session_id,
        role="assistant",
        content=prose_content,
        turn_number=turn,
        tool_calls=json.dumps(tool_call_records) if tool_call_records else None,
        generation_plan=plan_json,
        thinking_content=thinking_text,
        is_active_variant=True,
        created_at=msg_now,
    )
    await chats_db.create_message(asst_msg)
    logger.debug("%s Assistant message saved: id=%d, content=%d chars", lp, msg_id, len(prose_content))

    # Update session
    chat.current_turn = turn
    chat.character_stats = chats_db.serialize_stats(new_char)
    chat.world_stats = chats_db.serialize_stats(new_world)
    chat.modified_at = now()
    await chats_db.update_session(chat)
    logger.debug("%s Session updated: turn=%d", lp, turn)

    # Save/update snapshot
    snap_data = {
        "session_id": session_id,
        "turn_number": turn,
        "location_id": chat.current_location_id,
        "character_stats": chats_db.serialize_stats(new_char),
        "world_stats": chats_db.serialize_stats(new_world),
    }
    if is_regenerate:
        snap = await chats_db.get_snapshot_at_turn(session_id, turn)
        if snap:
            snap.character_stats = snap_data["character_stats"]
            snap.world_stats = snap_data["world_stats"]
            snap.location_id = snap_data["location_id"]
            await chats_db.update_snapshot(snap)
        else:
            await chats_db.create_snapshot(ChatStateSnapshot(
                id=snowflake_svc.generate_id(), created_at=now(), **snap_data,
            ))
    else:
        await chats_db.create_snapshot(ChatStateSnapshot(
            id=snowflake_svc.generate_id(), created_at=now(), **snap_data,
        ))

    # Emit done
    msg_resp = build_message_response(
        msg_id=msg_id,
        content=prose_content,
        turn_number=turn,
        created_at=msg_now,
        tool_calls=tool_call_records if tool_call_records else None,
        generation_plan=plan_json,
        thinking_content=thinking_text,
    )
    await queue.put(sse("done", {"message": msg_resp}))


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
    """Run the dynamic N-step chain pipeline: tool steps → writer step."""
    try:
        lp = _lp(session_id, turn)

        # Load world and parse pipeline
        world = await worlds_db.get_by_id(chat.world_id)
        if world is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
        try:
            pipeline = PipelineConfig.model_validate_json(world.pipeline)
        except Exception:
            pipeline = PipelineConfig(stages=[])

        logger.debug("%s Pipeline: %d stages, types=%s", lp, len(pipeline.stages), [s.step_type for s in pipeline.stages])
        if not pipeline.stages:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chain mode requires at least one pipeline stage")

        _migrate_legacy_stages(pipeline)

        # Build context and shared state
        context = await build_chat_context(chat)
        all_planning_contexts: list[PlanningContext] = []
        tool_call_records: list[dict[str, Any]] = []
        thinking_parts: list[dict[str, str]] = []
        prose_content = ""
        char_stats = chats_db.parse_stats(chat.character_stats)
        world_stats = chats_db.parse_stats(chat.world_stats)
        director_decision: str = ""

        # Run pipeline stages
        for stage_idx, stage in enumerate(pipeline.stages):
            if stage.step_type == "tool":
                stage_label = stage.name or f"Tool step {stage_idx + 1}"
                stage_decision_state = DecisionState()
                thinking_text = await _run_tool_stage(
                    lp, stage, stage_idx, chat, context, llm_messages, queue, caller_role,
                    all_planning_contexts, char_stats, world_stats,
                    tool_call_records,
                    stage_decision_state, director_decision,
                )
                if stage_decision_state.decision:
                    director_decision = stage_decision_state.decision
                    logger.debug("%s Director decision committed: %s", lp, director_decision[:200])
                if thinking_text:
                    thinking_parts.append({"stage_name": stage_label, "content": thinking_text})
                # Refresh context (move_to_location may have changed it)
                chat_refreshed = await chats_db.get_session_by_id(session_id)
                if chat_refreshed:
                    context = await build_chat_context(chat_refreshed)
                    chat = chat_refreshed

            elif stage.step_type == "writer":
                stage_label = stage.name or "Writing"
                prose_content, thinking_text = await _run_writer_stage(
                    lp, stage, stage_idx, chat, session_id, context, queue, caller_role,
                    all_planning_contexts, char_stats, world_stats,
                    tool_call_records, director_decision,
                )
                if thinking_text:
                    thinking_parts.append({"stage_name": stage_label, "content": thinking_text})

        await _finalize_chain(
            lp, chat, turn, session_id, queue, prose_content,
            char_stats, world_stats, all_planning_contexts,
            tool_call_records, thinking_parts, is_regenerate,
        )

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
    variant_index: int | None = None,
) -> AsyncGenerator[str, None]:
    """Chain mode generation: planning → writing pipeline."""

    async def _stream() -> AsyncGenerator[str, None]:
        chat = await chats_db.get_session_by_id(session_id)
        if chat is None or chat.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        if chat.status != "active":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chat is not active")

        turn = chat.current_turn + 1
        logger.debug("[s:%d] Starting chain generation, current_turn=%d", session_id, chat.current_turn)

        # Handle variant selection + clear variants atomically
        from app.services.chat_service import _load_variants, _save_variants
        variants = _load_variants(chat)
        if variant_index is not None and 0 <= variant_index < len(variants):
            # Swap chosen variant back as active assistant message
            from app.services.chat_service import continue_chat
            await continue_chat(session_id, chat.user_id, variant_index)
            chat = await chats_db.get_session_by_id(session_id)  # reload after swap
        elif variants:
            # No specific variant chosen — clear variants (auto-commit current)
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
        logger.debug("[s:%d] Starting chain regeneration, turn=%d", session_id, turn)

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
            logger.debug("[s:%d] Moved assistant msg %d to variants (now %d variants)", session_id, current_asst.id, len(variants))

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
