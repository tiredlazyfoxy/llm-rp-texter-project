"""World stat definition data access. Session-free public API."""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.world import WorldStatDefinition


async def get_by_id(stat_id: int) -> WorldStatDefinition | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(WorldStatDefinition).where(WorldStatDefinition.id == stat_id))).one_or_none()


async def list_by_world(world_id: int) -> list[WorldStatDefinition]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(
            select(WorldStatDefinition).where(WorldStatDefinition.world_id == world_id)
        )).all())


async def create(stat: WorldStatDefinition) -> WorldStatDefinition:
    session = await get_standalone_session()
    async with session:
        session.add(stat)
        await session.commit()
        await session.refresh(stat)
        return stat


async def update(stat: WorldStatDefinition) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(stat)
        await session.commit()


async def delete(stat_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        stat = (await session.exec(
            select(WorldStatDefinition).where(WorldStatDefinition.id == stat_id)
        )).one_or_none()
        if stat is None:
            return False
        await session.delete(stat)
        await session.commit()
        return True
