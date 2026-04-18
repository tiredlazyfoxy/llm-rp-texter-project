"""Summarization service — two-phase SSE-streamed compaction + un-summarize.

Phase 1: Memory extraction — agentic call with add_memory tool (non-streaming).
Phase 2: Narrative summarization — streaming token-by-token summary generation.

SSE events emitted:
  phase            — {"phase": "memory_extraction"|"summarization"}
  tool_call_start  — {"tool_name": "add_memory", "arguments": {...}, "stage_name": "Memory Extraction"}
  tool_call_result — {"tool_name": "add_memory", "result": "..."}
  token            — {"content": "..."}  (summary text during phase 2)
  compact_done     — {"summary": {...}, "updated_message_count": N}
  error            — {"detail": "..."}
"""

import asyncio
import functools
import json
import logging
import re
from collections.abc import AsyncGenerator, Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.db import chats as chats_db
from app.models.chat_summary import ChatSummary
from app.models.schemas.chat import ChatMessageResponse, ChatSummaryResponse, GenerationVariant
from app.services import snowflake as snowflake_svc
from app.services.chat_tools import ToolContext, build_tools
from app.services.llm_chat import get_llm_client_for_model
from app.services.prompts import (
    MEMORY_EXTRACTION_SYSTEM_PROMPT,
    MEMORY_EXTRACTION_USER_PROMPT_TEMPLATE,
    SUMMARIZE_SYSTEM_PROMPT,
    SUMMARIZE_USER_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sse(event: str, data: dict[str, Any]) -> str:
    """Format a Server-Sent Event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _format_messages_for_summary(messages: list[Any]) -> str:
    """Format chat messages into a text block for the LLM summarizer."""
    lines: list[str] = []
    for m in messages:
        role_label = m.role.capitalize()
        lines.append(f"Turn {m.turn_number} - {role_label}: {m.content}")
    return "\n".join(lines)


def _load_variants(session: Any) -> list[GenerationVariant]:
    """Parse generation_variants JSON from session."""
    try:
        raw = json.loads(session.generation_variants)
        return [GenerationVariant.model_validate(v) for v in raw]
    except Exception:
        return []


def _make_tool_wrapper(
    name: str,
    fn: Callable[..., Any],
    queue: asyncio.Queue[str | None],
    stage_name: str = "",
) -> Callable[..., Any]:
    """Wrap tool callable to emit SSE events via the queue."""
    @functools.wraps(fn)
    async def wrapper(**kwargs: Any) -> str:
        logger.debug("Compact tool call: %s(%s)", name, kwargs)
        await queue.put(_sse("tool_call_start", {
            "tool_name": name, "arguments": {k: str(v) for k, v in kwargs.items()},
            "stage_name": stage_name,
        }))
        try:
            result = await fn(**kwargs)
        except Exception as exc:
            error_msg = f"Tool error: {exc}"
            await queue.put(_sse("tool_call_result", {"tool_name": name, "result": error_msg}))
            return error_msg
        await queue.put(_sse("tool_call_result", {"tool_name": name, "result": result}))
        return result
    return wrapper


# ---------------------------------------------------------------------------
# Two-phase SSE compact stream
# ---------------------------------------------------------------------------

async def compact_messages_stream(
    session_id: int,
    up_to_message_id: int,
    user_id: int,
    variant_index: int | None = None,
) -> AsyncGenerator[str, None]:
    """Summarize messages via two-phase SSE stream.

    Yields SSE event strings (phase, tool_call_start/result, token, compact_done, error).
    """
    try:
        # 1. Load and verify session
        chat = await chats_db.get_session_by_id(session_id)
        if chat is None or chat.user_id != user_id:
            yield _sse("error", {"detail": "Chat not found"})
            return
        if chat.status != "active":
            yield _sse("error", {"detail": "Chat is not active"})
            return

        # 2. Load and verify target message
        target_msg = await chats_db.get_message_by_id(up_to_message_id)
        if target_msg is None or target_msg.session_id != session_id:
            yield _sse("error", {"detail": "Message not found"})
            return
        if target_msg.role != "assistant":
            yield _sse("error", {"detail": "Can only compact up to an assistant message"})
            return

        # 3. Determine start point
        existing_summaries = await chats_db.list_summaries(session_id)
        if existing_summaries:
            last_summary = existing_summaries[-1]
            start_after_id = last_summary.end_message_id
        else:
            start_after_id = None

        # 4. Gather active, non-summarized messages in range
        all_active = await chats_db.list_active_messages(session_id)
        candidates: list[Any] = []
        past_start = start_after_id is None
        for m in all_active:
            if not past_start:
                if m.id == start_after_id:
                    past_start = True
                continue
            candidates.append(m)
            if m.id == up_to_message_id:
                break

        if not candidates:
            yield _sse("error", {"detail": "No messages to summarize in the specified range"})
            return

        # 5. Variant substitution — if compacting current turn with a specific variant
        formatted_messages = list(candidates)  # shallow copy for content override
        if variant_index is not None:
            last_candidate = candidates[-1]
            if last_candidate.turn_number == chat.current_turn and last_candidate.role == "assistant":
                variants = _load_variants(chat)
                if 0 <= variant_index < len(variants):
                    # Create a simple namespace to override content for formatting
                    class _Proxy:
                        def __init__(self, msg: Any, content: str) -> None:
                            self._msg = msg
                            self.content = content
                        def __getattr__(self, name: str) -> Any:
                            return getattr(self._msg, name)
                    formatted_messages[-1] = _Proxy(last_candidate, variants[variant_index].content)

        # 6. Format messages
        formatted = _format_messages_for_summary(formatted_messages)

        # 7. Verify model
        model_id = chat.text_model_id
        if not model_id:
            yield _sse("error", {"detail": "No text model configured for this chat"})
            return

        logger.info("Compact streaming %d messages for session %s", len(candidates), session_id)

        # ---------------------------------------------------------------
        # Phase 1: Memory extraction (agentic, non-streaming)
        # ---------------------------------------------------------------
        yield _sse("phase", {"phase": "memory_extraction"})

        queue: asyncio.Queue[str | None] = asyncio.Queue()

        ctx = ToolContext(session_id=session_id)
        tool_defs, tool_callables = build_tools(["add_memory"], ctx)

        # Counting wrapper: cap add_memory calls and return structured JSON
        MAX_MEMORIES_PER_COMPACT = 5
        saved_memories: list[str] = []
        original_add_memory = tool_callables["add_memory"]

        @functools.wraps(original_add_memory)
        async def _capped_add_memory(content: str) -> str:
            if len(saved_memories) >= MAX_MEMORIES_PER_COMPACT:
                return json.dumps({
                    "status": "rejected",
                    "reason": "memory_limit_reached",
                    "limit": MAX_MEMORIES_PER_COMPACT,
                    "already_saved": saved_memories,
                    "message": "Maximum memories already saved. Stop calling add_memory.",
                })
            await original_add_memory(content=content)
            saved_memories.append(content)
            return json.dumps({
                "status": "ok",
                "saved_count": len(saved_memories),
                "remaining": MAX_MEMORIES_PER_COMPACT - len(saved_memories),
                "already_saved": saved_memories,
            })

        # Wrap for SSE emission
        wrapped: dict[str, Callable[..., Any]] = {
            "add_memory": _make_tool_wrapper("add_memory", _capped_add_memory, queue, stage_name="Memory Extraction"),
        }

        from llm.message import LLMMessage

        # Load existing memories to avoid duplicates
        existing_memories = await chats_db.list_memories(session_id)
        if existing_memories:
            existing_memories_text = "\n".join(
                f"- {m.content}" for m in existing_memories
            )
        else:
            existing_memories_text = "(none yet)"

        memory_user_prompt = MEMORY_EXTRACTION_USER_PROMPT_TEMPLATE.format(
            messages=formatted,
            existing_memories=existing_memories_text,
        )
        memory_messages: list[LLMMessage] = [{"role": "user", "content": memory_user_prompt}]

        async def run_memory_extraction() -> None:
            try:
                client = await get_llm_client_for_model(model_id)
                async with client:
                    await client.chat_with_tools(
                        memory_messages,
                        tools_definitions=tool_defs,
                        tools=wrapped,
                        system=MEMORY_EXTRACTION_SYSTEM_PROMPT,
                        options={"temperature": 0.3},
                        max_loops=10,
                        stream=False,
                    )
            except Exception as exc:
                logger.exception("Memory extraction LLM error")
                await queue.put(_sse("error", {"detail": str(exc)}))
            finally:
                await queue.put(None)

        mem_task = asyncio.create_task(run_memory_extraction())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            if not mem_task.done():
                mem_task.cancel()

        # ---------------------------------------------------------------
        # Phase 2: Summarization (streaming tokens)
        # ---------------------------------------------------------------
        yield _sse("phase", {"phase": "summarization"})

        summary_user_prompt = SUMMARIZE_USER_PROMPT_TEMPLATE.format(messages=formatted)
        summary_messages: list[LLMMessage] = [{"role": "user", "content": summary_user_prompt}]

        content_parts: list[str] = []
        _in_thinking = False

        async def on_delta(delta: str) -> None:
            nonlocal _in_thinking
            # Filter out <think>...</think> reasoning content from the LLM client
            if "<think>" in delta:
                _in_thinking = True
                # Keep any text before the <think> tag
                before = delta.split("<think>")[0]
                if before:
                    content_parts.append(before)
                    await queue.put(_sse("token", {"content": before}))
                return
            if _in_thinking:
                if "</think>" in delta:
                    _in_thinking = False
                    # Keep any text after the </think> tag
                    after = delta.split("</think>", 1)[1]
                    if after:
                        content_parts.append(after)
                        await queue.put(_sse("token", {"content": after}))
                return
            content_parts.append(delta)
            await queue.put(_sse("token", {"content": delta}))

        async def run_summary_llm() -> None:
            try:
                client2 = await get_llm_client_for_model(model_id)
                async with client2:
                    await client2.chat(
                        summary_messages,
                        system=SUMMARIZE_SYSTEM_PROMPT,
                        options={"temperature": 0.3},
                        stream=True,
                        on_delta=on_delta,
                    )
            except Exception as exc:
                logger.exception("Summarization LLM error")
                await queue.put(_sse("error", {"detail": str(exc)}))
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_summary_llm())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            if not task.done():
                task.cancel()

        summary_content = re.sub(r"<think>[\s\S]*?</think>", "", "".join(content_parts)).strip()
        if not summary_content:
            yield _sse("error", {"detail": "LLM returned empty summary"})
            return

        # 8. Create summary record
        first_msg = candidates[0]
        last_msg = candidates[-1]
        summary = ChatSummary(
            id=snowflake_svc.generate_id(),
            session_id=session_id,
            start_message_id=first_msg.id,
            end_message_id=last_msg.id,
            start_turn=first_msg.turn_number,
            end_turn=last_msg.turn_number,
            content=summary_content,
            created_at=_now(),
        )
        summary = await chats_db.create_summary(summary)

        # 9. Link messages to summary
        msg_ids = [m.id for m in candidates]
        count = await chats_db.set_summary_id_on_messages(msg_ids, summary.id)

        # 9b. If we summarized through the current turn, clear variants (persist to DB)
        if last_msg.turn_number >= chat.current_turn:
            chat.generation_variants = "[]"
            chat.modified_at = _now()
            await chats_db.update_session(chat)

        logger.info("Created summary %s covering turns %d-%d (%d messages)",
                     summary.id, summary.start_turn, summary.end_turn, count)

        # 10. Emit compact_done
        summary_resp = ChatSummaryResponse(
            id=str(summary.id),
            start_message_id=str(summary.start_message_id),
            end_message_id=str(summary.end_message_id),
            start_turn=summary.start_turn,
            end_turn=summary.end_turn,
            content=summary.content,
            created_at=summary.created_at.isoformat(),
        )
        yield _sse("compact_done", {
            "summary": summary_resp.model_dump(),
            "updated_message_count": count,
        })

    except Exception as exc:
        logger.exception("Compact stream error for session %s", session_id)
        yield _sse("error", {"detail": str(exc)})


# ---------------------------------------------------------------------------
# Un-summarize (revert last summary)
# ---------------------------------------------------------------------------

async def unsummarize_last(
    session_id: int,
    summary_id: int,
    user_id: int,
) -> list[ChatMessageResponse]:
    """Revert the last summary — delete record, unlink messages, return restored messages.

    Only the last summary in the ordered list can be reverted.
    """
    from app.services.chat_service import _msg_to_response

    # 1. Verify session ownership
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    # 2. Verify this is the last summary
    summaries = await chats_db.list_summaries(session_id)
    if not summaries or summaries[-1].id != summary_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only revert the last summary",
        )

    # 3. Fetch messages linked to this summary (before deleting)
    messages = await chats_db.list_messages_by_summary_id(summary_id)

    # 4. Delete summary (also sets summary_id=NULL on linked messages)
    deleted = await chats_db.delete_summary(summary_id, session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary not found",
        )

    logger.info("Un-summarized summary %s for session %s (%d messages restored)",
                summary_id, session_id, len(messages))

    return [_msg_to_response(m) for m in messages]


# ---------------------------------------------------------------------------
# Regenerate (kept from original — non-streaming single LLM call)
# ---------------------------------------------------------------------------

async def regenerate_summary(
    summary_id: int,
    user_id: int,
) -> ChatSummary:
    """Re-generate an existing summary with a new LLM call."""
    # 1. Load summary and verify ownership
    summary = await chats_db.get_summary_by_id(summary_id)
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found")

    chat = await chats_db.get_session_by_id(summary.session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    # 2. Load original messages
    messages = await chats_db.list_messages_by_summary_id(summary_id)
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No messages found for this summary",
        )

    # 3. Format and call LLM
    formatted = _format_messages_for_summary(messages)
    user_prompt = SUMMARIZE_USER_PROMPT_TEMPLATE.format(messages=formatted)

    model_id = chat.text_model_id
    if not model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No text model configured for this chat",
        )

    client = await get_llm_client_for_model(model_id)
    from llm.message import LLMMessage

    llm_messages: list[LLMMessage] = [{"role": "user", "content": user_prompt}]
    async with client:
        response = await client.chat(
            llm_messages,
            system=SUMMARIZE_SYSTEM_PROMPT,
            options={"temperature": 0.3},
        )

    new_content = response.strip() if response else ""
    if not new_content:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM returned empty summary",
        )

    # 4. Update summary content
    summary.content = new_content
    await chats_db.update_summary(summary)

    logger.info("Regenerated summary %s", summary_id)
    return summary
