"""Chat data access. Session-free public API — all sessions managed internally."""

import json
import logging
from datetime import datetime, timezone

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.chat_state_snapshot import ChatStateSnapshot
from app.models.chat_summary import ChatSummary

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ChatSession
# ---------------------------------------------------------------------------

async def get_session_by_id(session_id: int) -> ChatSession | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(
            select(ChatSession).where(ChatSession.id == session_id)
        )).one_or_none()


async def list_sessions_by_user(user_id: int) -> list[ChatSession]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.modified_at.desc())  # type: ignore[arg-type]
        )).all())


async def create_session(chat: ChatSession) -> ChatSession:
    session = await get_standalone_session()
    async with session:
        session.add(chat)
        await session.commit()
        await session.refresh(chat)
        return chat


async def update_session(chat: ChatSession) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(chat)
        await session.commit()


async def delete_session(session_id: int) -> bool:
    """Delete chat session and all related rows (FK order)."""
    db = await get_standalone_session()
    async with db:
        # delete summaries first (messages FK to summaries)
        summaries = (await db.exec(
            select(ChatSummary).where(ChatSummary.session_id == session_id)
        )).all()
        for s in summaries:
            await db.delete(s)

        snapshots = (await db.exec(
            select(ChatStateSnapshot).where(ChatStateSnapshot.session_id == session_id)
        )).all()
        for s in snapshots:
            await db.delete(s)

        messages = (await db.exec(
            select(ChatMessage).where(ChatMessage.session_id == session_id)
        )).all()
        for m in messages:
            await db.delete(m)

        chat = (await db.exec(
            select(ChatSession).where(ChatSession.id == session_id)
        )).one_or_none()
        if chat is None:
            await db.rollback()
            return False
        await db.delete(chat)
        await db.commit()
        return True


# ---------------------------------------------------------------------------
# ChatMessage
# ---------------------------------------------------------------------------

async def create_message(msg: ChatMessage) -> ChatMessage:
    session = await get_standalone_session()
    async with session:
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg


async def get_message_by_id(msg_id: int) -> ChatMessage | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(
            select(ChatMessage).where(ChatMessage.id == msg_id)
        )).one_or_none()


async def list_active_messages(session_id: int) -> list[ChatMessage]:
    """Active variant messages with no summary (for display)."""
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.summary_id.is_(None))  # type: ignore[union-attr]
            .where(ChatMessage.is_active_variant == True)  # noqa: E712
            .order_by(ChatMessage.turn_number.asc())  # type: ignore[arg-type]
        )).all())


async def list_variants_for_turn(session_id: int, turn_number: int) -> list[ChatMessage]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.turn_number == turn_number)
            .where(ChatMessage.role == "assistant")
        )).all())


async def get_active_assistant_at_turn(session_id: int, turn_number: int) -> ChatMessage | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.turn_number == turn_number)
            .where(ChatMessage.role == "assistant")
            .where(ChatMessage.is_active_variant == True)  # noqa: E712
        )).one_or_none()


async def get_user_message_at_turn(session_id: int, turn_number: int) -> ChatMessage | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.turn_number == turn_number)
            .where(ChatMessage.role == "user")
        )).one_or_none()


async def set_message_inactive(msg_id: int) -> None:
    session = await get_standalone_session()
    async with session:
        msg = (await session.exec(
            select(ChatMessage).where(ChatMessage.id == msg_id)
        )).one_or_none()
        if msg:
            msg.is_active_variant = False
            await session.merge(msg)
            await session.commit()


async def delete_messages_after_turn(session_id: int, target_turn: int) -> None:
    session = await get_standalone_session()
    async with session:
        rows = (await session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.turn_number > target_turn)
        )).all()
        for r in rows:
            await session.delete(r)
        await session.commit()


async def delete_non_selected_variants(session_id: int, turn_number: int, keep_id: int) -> None:
    session = await get_standalone_session()
    async with session:
        rows = (await session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.turn_number == turn_number)
            .where(ChatMessage.role == "assistant")
            .where(ChatMessage.id != keep_id)
        )).all()
        for r in rows:
            await session.delete(r)
        # Ensure selected is active
        selected = (await session.exec(
            select(ChatMessage).where(ChatMessage.id == keep_id)
        )).one_or_none()
        if selected:
            selected.is_active_variant = True
            await session.merge(selected)
        await session.commit()


async def update_message(msg: ChatMessage) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(msg)
        await session.commit()


# ---------------------------------------------------------------------------
# ChatStateSnapshot
# ---------------------------------------------------------------------------

async def create_snapshot(snap: ChatStateSnapshot) -> ChatStateSnapshot:
    session = await get_standalone_session()
    async with session:
        session.add(snap)
        await session.commit()
        await session.refresh(snap)
        return snap


async def list_snapshots(session_id: int) -> list[ChatStateSnapshot]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(
            select(ChatStateSnapshot)
            .where(ChatStateSnapshot.session_id == session_id)
            .order_by(ChatStateSnapshot.turn_number.asc())  # type: ignore[arg-type]
        )).all())


async def get_snapshot_at_turn(session_id: int, turn_number: int) -> ChatStateSnapshot | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(
            select(ChatStateSnapshot)
            .where(ChatStateSnapshot.session_id == session_id)
            .where(ChatStateSnapshot.turn_number == turn_number)
        )).one_or_none()


async def update_snapshot(snap: ChatStateSnapshot) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(snap)
        await session.commit()


async def delete_snapshots_after_turn(session_id: int, target_turn: int) -> None:
    session = await get_standalone_session()
    async with session:
        rows = (await session.exec(
            select(ChatStateSnapshot)
            .where(ChatStateSnapshot.session_id == session_id)
            .where(ChatStateSnapshot.turn_number > target_turn)
        )).all()
        for r in rows:
            await session.delete(r)
        await session.commit()


# ---------------------------------------------------------------------------
# ChatSummary
# ---------------------------------------------------------------------------

async def list_summaries(session_id: int) -> list[ChatSummary]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(
            select(ChatSummary)
            .where(ChatSummary.session_id == session_id)
            .order_by(ChatSummary.start_turn.asc())  # type: ignore[arg-type]
        )).all())


async def get_summary_by_id(summary_id: int) -> ChatSummary | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(
            select(ChatSummary).where(ChatSummary.id == summary_id)
        )).one_or_none()


async def delete_summary(summary_id: int, session_id: int) -> bool:
    """Delete summary and unlink messages (set summary_id=NULL)."""
    db = await get_standalone_session()
    async with db:
        summary = (await db.exec(
            select(ChatSummary)
            .where(ChatSummary.id == summary_id)
            .where(ChatSummary.session_id == session_id)
        )).one_or_none()
        if summary is None:
            return False
        # Unlink messages
        msgs = (await db.exec(
            select(ChatMessage).where(ChatMessage.summary_id == summary_id)
        )).all()
        for m in msgs:
            m.summary_id = None
            await db.merge(m)
        await db.delete(summary)
        await db.commit()
        return True


async def delete_summaries_after_turn(session_id: int, target_turn: int) -> None:
    """Delete summaries whose end_turn > target_turn; unlink messages from partial ones."""
    db = await get_standalone_session()
    async with db:
        summaries = (await db.exec(
            select(ChatSummary)
            .where(ChatSummary.session_id == session_id)
            .where(ChatSummary.end_turn > target_turn)
        )).all()
        for summary in summaries:
            msgs = (await db.exec(
                select(ChatMessage).where(ChatMessage.summary_id == summary.id)
            )).all()
            for m in msgs:
                m.summary_id = None
                await db.merge(m)
            await db.delete(summary)
        await db.commit()


async def create_summary(summary: ChatSummary) -> ChatSummary:
    session = await get_standalone_session()
    async with session:
        session.add(summary)
        await session.commit()
        await session.refresh(summary)
        return summary


async def update_summary(summary: ChatSummary) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(summary)
        await session.commit()


async def list_messages_by_summary_id(summary_id: int) -> list[ChatMessage]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(
            select(ChatMessage)
            .where(ChatMessage.summary_id == summary_id)
            .order_by(ChatMessage.turn_number.asc(), ChatMessage.created_at.asc())  # type: ignore[arg-type]
        )).all())


async def set_summary_id_on_messages(message_ids: list[int], summary_id: int) -> int:
    """Bulk-set summary_id on messages. Returns count of affected rows."""
    if not message_ids:
        return 0
    session = await get_standalone_session()
    async with session:
        msgs = (await session.exec(
            select(ChatMessage).where(ChatMessage.id.in_(message_ids))  # type: ignore[arg-type]
        )).all()
        for m in msgs:
            m.summary_id = summary_id
            await session.merge(m)
        await session.commit()
        return len(msgs)


# ---------------------------------------------------------------------------
# Helpers used by service layer
# ---------------------------------------------------------------------------

def parse_stats(raw: str) -> dict[str, int | str | list[str]]:
    try:
        return json.loads(raw)
    except Exception:
        return {}


def serialize_stats(stats: dict[str, int | str | list[str]]) -> str:
    return json.dumps(stats)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
