"""Chat generation feedback data access. Session-free public API."""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.chat_generation_feedback import ChatGenerationFeedback


async def create(feedback: ChatGenerationFeedback) -> ChatGenerationFeedback:
    session = await get_standalone_session()
    async with session:
        session.add(feedback)
        await session.commit()
        await session.refresh(feedback)
        return feedback


async def list_by_turn(session_id: int, turn_number: int) -> list[ChatGenerationFeedback]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(
            select(ChatGenerationFeedback)
            .where(ChatGenerationFeedback.session_id == session_id)
            .where(ChatGenerationFeedback.turn_number == turn_number)
            .order_by(ChatGenerationFeedback.created_at)  # type: ignore[arg-type]
        )).all())


async def list_by_session(session_id: int) -> list[ChatGenerationFeedback]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(
            select(ChatGenerationFeedback)
            .where(ChatGenerationFeedback.session_id == session_id)
            .order_by(ChatGenerationFeedback.created_at)  # type: ignore[arg-type]
        )).all())


async def delete_by_session(session_id: int) -> int:
    session = await get_standalone_session()
    async with session:
        rows = (await session.exec(
            select(ChatGenerationFeedback)
            .where(ChatGenerationFeedback.session_id == session_id)
        )).all()
        for row in rows:
            await session.delete(row)
        await session.commit()
        return len(rows)
