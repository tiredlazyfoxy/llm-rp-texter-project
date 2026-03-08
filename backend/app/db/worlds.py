"""World data access. Session-free public API — all sessions managed internally."""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.world import World


async def get_by_id(world_id: int) -> World | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(World).where(World.id == world_id))).one_or_none()


async def list_all() -> list[World]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(select(World))).all())


async def create(world: World) -> World:
    session = await get_standalone_session()
    async with session:
        session.add(world)
        await session.commit()
        await session.refresh(world)
        return world


async def update(world: World) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(world)
        await session.commit()


async def delete(world_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        world = (await session.exec(select(World).where(World.id == world_id))).one_or_none()
        if world is None:
            return False
        await session.delete(world)
        await session.commit()
        return True
