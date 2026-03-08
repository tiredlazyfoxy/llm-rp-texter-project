"""User data access. Session-free public API — all sessions managed internally."""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.user import User


async def get_by_id(user_id: int) -> User | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(User).where(User.id == user_id))).one_or_none()


async def get_by_username(username: str) -> User | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(User).where(User.username == username))).one_or_none()


async def create(user: User) -> User:
    session = await get_standalone_session()
    async with session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def get_all() -> list[User]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(select(User).order_by(User.username))).all())


async def update(user: User) -> None:
    session = await get_standalone_session()
    async with session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
