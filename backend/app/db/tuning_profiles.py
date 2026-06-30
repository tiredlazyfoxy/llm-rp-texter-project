"""Chat tuning profile data access. Session-free public API."""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.chat_tuning_profile import ChatTuningProfile


async def get(user_id: int, world_id: int) -> ChatTuningProfile | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(
            select(ChatTuningProfile)
            .where(ChatTuningProfile.user_id == user_id)
            .where(ChatTuningProfile.world_id == world_id)
        )).one_or_none()


async def upsert(profile: ChatTuningProfile) -> ChatTuningProfile:
    session = await get_standalone_session()
    async with session:
        merged = await session.merge(profile)
        await session.commit()
        await session.refresh(merged)
        return merged
