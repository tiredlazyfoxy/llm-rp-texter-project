"""User settings data access. Session-free public API."""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.user_settings import UserSettings


async def get(user_id: int) -> UserSettings | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(UserSettings).where(UserSettings.user_id == user_id))).one_or_none()


async def upsert(settings: UserSettings) -> UserSettings:
    session = await get_standalone_session()
    async with session:
        merged = await session.merge(settings)
        await session.commit()
        await session.refresh(merged)
        return merged
