"""Summarization service — compacts older chat messages into LLM-generated summaries."""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.db import chats as chats_db
from app.models.chat_summary import ChatSummary
from app.services import snowflake as snowflake_svc
from app.services.llm_chat import get_llm_client_for_model
from app.services.prompts import SUMMARIZE_SYSTEM_PROMPT, SUMMARIZE_USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _format_messages_for_summary(messages: list) -> str:
    """Format chat messages into a text block for the LLM summarizer."""
    lines: list[str] = []
    for m in messages:
        role_label = m.role.capitalize()
        lines.append(f"Turn {m.turn_number} - {role_label}: {m.content}")
    return "\n".join(lines)


async def compact_messages(
    session_id: int,
    up_to_message_id: int,
    user_id: int,
) -> tuple[ChatSummary, int]:
    """Summarize messages from start (or after last summary) up to the given message.

    Returns (new_summary, count_of_messages_linked).
    """
    # 1. Load and verify session
    chat = await chats_db.get_session_by_id(session_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    if chat.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chat is not active")

    # 2. Load and verify target message
    target_msg = await chats_db.get_message_by_id(up_to_message_id)
    if target_msg is None or target_msg.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if target_msg.role != "assistant":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only compact up to an assistant message",
        )

    # 3. Determine start point
    existing_summaries = await chats_db.list_summaries(session_id)
    if existing_summaries:
        last_summary = existing_summaries[-1]
        start_after_id = last_summary.end_message_id
    else:
        start_after_id = None

    # 4. Gather active, non-summarized messages in range
    all_active = await chats_db.list_active_messages(session_id)
    # list_active_messages already filters: summary_id IS NULL, is_active_variant=True, ordered by turn_number
    candidates: list = []
    past_start = start_after_id is None
    for m in all_active:
        if not past_start:
            if m.id == start_after_id:
                past_start = True
            continue
        candidates.append(m)
        if m.id == up_to_message_id:
            break

    # 5. Validate
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No messages to summarize in the specified range",
        )

    # 6. Format messages
    formatted = _format_messages_for_summary(candidates)
    user_prompt = SUMMARIZE_USER_PROMPT_TEMPLATE.format(messages=formatted)

    # 7. Call LLM (non-streaming)
    model_id = chat.text_model_id
    if not model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No text model configured for this chat",
        )

    logger.info("Summarizing %d messages for session %s", len(candidates), session_id)

    client = await get_llm_client_for_model(model_id)
    from llm.message import LLMMessage

    llm_messages: list[LLMMessage] = [{"role": "user", "content": user_prompt}]
    async with client:
        response = await client.chat(
            llm_messages,
            system=SUMMARIZE_SYSTEM_PROMPT,
            options={"temperature": 0.3},
        )

    summary_content = response.strip() if response else ""
    if not summary_content:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM returned empty summary",
        )

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

    logger.info("Created summary %s covering turns %d-%d (%d messages)",
                summary.id, summary.start_turn, summary.end_turn, count)

    return summary, count


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
