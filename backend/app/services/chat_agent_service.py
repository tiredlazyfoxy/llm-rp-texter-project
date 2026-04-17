"""Chat agent service — generation dispatcher and shared helpers.

Routes generate/regenerate requests to the appropriate mode-specific service
based on World.generation_mode. Also provides shared utilities used by all
generation services.
"""

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator, Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.db import chats as chats_db
from app.db import worlds as worlds_db
from app.models.schemas.chat import ChatMessageResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers (used by simple_generation_service, chain_generation_service)
# ---------------------------------------------------------------------------

def _lp(session_id: int, turn: int) -> str:
    """Log prefix for session/turn tracing."""
    return f"[s:{session_id} t:{turn}]"



def sse(event: str, data: dict) -> str:
    """Format a Server-Sent Event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def now() -> datetime:
    """UTC timestamp."""
    return datetime.now(timezone.utc)


def parse_stat_updates(content: str) -> dict[str, Any]:
    """Extract [STAT_UPDATE] block from assistant response."""
    match = re.search(r"\[STAT_UPDATE\](.*?)\[/STAT_UPDATE\]", content, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1).strip())
    except Exception:
        return {}


def strip_stat_block(content: str) -> str:
    """Remove [STAT_UPDATE]...[/STAT_UPDATE] from display content."""
    return re.sub(
        r"\[STAT_UPDATE\].*?\[/STAT_UPDATE\]", "", content, flags=re.DOTALL
    ).strip()


def build_message_response(
    msg_id: int,
    content: str,
    turn_number: int,
    created_at: datetime,
    tool_calls: list[dict] | None = None,
    generation_plan: str | None = None,
    thinking_content: str | None = None,
) -> dict:
    """Build a ChatMessageResponse dict for the done SSE event."""
    from app.models.schemas.chat import ToolCallInfo

    tc_list = None
    if tool_calls:
        tc_list = [
            ToolCallInfo(
                tool_name=tc["tool_name"],
                arguments=tc["arguments"],
                result=tc["result"],
                stage_name=tc.get("stage_name"),
            ).model_dump()
            for tc in tool_calls
        ]

    resp = ChatMessageResponse(
        id=str(msg_id),
        role="assistant",
        content=content,
        turn_number=turn_number,
        tool_calls=tc_list,
        generation_plan=generation_plan,
        thinking_content=thinking_content,
        is_active_variant=True,
        created_at=created_at.isoformat(),
    )
    return resp.model_dump()


async def build_llm_messages(session_id: int) -> list[dict[str, str]]:
    """Build LLM message list: summary blocks + non-summarized active messages."""
    llm_messages: list[dict[str, str]] = []

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

    logger.debug(
        "[s:%d] Built LLM messages: %d summaries, %d active, %d total",
        session_id, len(summaries), len(active_msgs), len(llm_messages),
    )
    return llm_messages


def create_thinking_callback(
    queue: asyncio.Queue,
    content_parts: list[str],
    thinking_parts: list[str] | None = None,
) -> Callable:
    """Factory for on_delta callback with <think>/<\/think> tag detection.

    Returns an async callback that:
    - Detects <think> / </think> tags in the token stream
    - Emits 'thinking' SSE events for reasoning content
    - Emits 'thinking_done' when reasoning ends
    - Emits 'token' SSE events for narrative content
    - Accumulates non-thinking content in content_parts
    - Accumulates thinking content in thinking_parts (if provided)
    """
    state = {"in_thinking": False}

    async def on_delta(delta: str) -> None:
        text = delta
        if not state["in_thinking"] and "<think>" in text:
            idx = text.index("<think>")
            before = text[:idx]
            after = text[idx + 7:]
            if before:
                content_parts.append(before)
                await queue.put(sse("token", {"content": before}))
            state["in_thinking"] = True
            if after:
                if thinking_parts is not None:
                    thinking_parts.append(after)
                await queue.put(sse("thinking", {"content": after}))
            return
        if state["in_thinking"] and "</think>" in text:
            idx = text.index("</think>")
            before = text[:idx]
            after = text[idx + 8:]
            if before:
                if thinking_parts is not None:
                    thinking_parts.append(before)
                await queue.put(sse("thinking", {"content": before}))
            await queue.put(sse("thinking_done", {}))
            state["in_thinking"] = False
            if after:
                content_parts.append(after)
                await queue.put(sse("token", {"content": after}))
            return
        if state["in_thinking"]:
            if thinking_parts is not None:
                thinking_parts.append(text)
            await queue.put(sse("thinking", {"content": text}))
        else:
            content_parts.append(text)
            await queue.put(sse("token", {"content": text}))

    return on_delta


# ---------------------------------------------------------------------------
# Dispatch: generate_response
# ---------------------------------------------------------------------------

async def generate_response(
    session_id: int,
    user_id: int,
    user_message: str,
    caller_role: str = "player",
    variant_index: int | None = None,
    user_instructions: str | None = None,
) -> AsyncGenerator[str, None]:
    """Dispatch to mode-specific generation service."""
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    if chat.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chat is not active")

    world = await worlds_db.get_by_id(chat.world_id)
    if world is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")

    mode = world.generation_mode or "simple"
    logger.debug("[s:%d] Dispatching generation: mode=%s, world_id=%d", session_id, mode, world.id)

    if mode == "chain":
        from app.services import chain_generation_service
        return chain_generation_service.generate_chain_response(
            session_id, user_id, user_message, caller_role,
            variant_index=variant_index,
            user_instructions=user_instructions,
        )
    elif mode == "agentic":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agentic mode not yet implemented",
        )
    else:
        from app.services import simple_generation_service
        return simple_generation_service.generate_simple_response(
            session_id, user_id, user_message,
            variant_index=variant_index,
            user_instructions=user_instructions,
        )


# ---------------------------------------------------------------------------
# Dispatch: regenerate_response
# ---------------------------------------------------------------------------

async def regenerate_response(
    session_id: int,
    user_id: int,
    caller_role: str = "player",
    turn_number: int | None = None,
) -> AsyncGenerator[str, None]:
    """Dispatch to mode-specific regeneration service.

    If turn_number is specified and < current_turn, rewinds first.
    """
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    if chat.status != "active" or chat.current_turn == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot regenerate")

    logger.debug(
        "[s:%d] Dispatching regeneration: turn=%d, rewind_to=%s",
        session_id, chat.current_turn, turn_number,
    )

    # If turn_number specified and < current_turn, rewind first
    if turn_number is not None and turn_number < chat.current_turn:
        from app.services import chat_service
        await chat_service.rewind_chat(session_id, user_id, turn_number, caller_role)
        # Reload chat after rewind
        chat = await chats_db.get_session_by_id(session_id)
        if chat is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    world = await worlds_db.get_by_id(chat.world_id)
    if world is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")

    mode = world.generation_mode or "simple"

    if mode == "chain":
        from app.services import chain_generation_service
        return chain_generation_service.regenerate_chain_response(
            session_id, user_id, caller_role,
        )
    elif mode == "agentic":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agentic mode not yet implemented",
        )
    else:
        from app.services import simple_generation_service
        return simple_generation_service.regenerate_simple_response(
            session_id, user_id,
        )
