"""World location data access. Session-free public API."""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.world import WorldLocation


async def get_by_id(location_id: int) -> WorldLocation | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(WorldLocation).where(WorldLocation.id == location_id))).one_or_none()


async def list_by_world(world_id: int) -> list[WorldLocation]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(select(WorldLocation).where(WorldLocation.world_id == world_id))).all())


async def create(location: WorldLocation) -> WorldLocation:
    session = await get_standalone_session()
    async with session:
        session.add(location)
        await session.commit()
        await session.refresh(location)
        return location


async def update(location: WorldLocation) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(location)
        await session.commit()


async def delete_by_world(world_id: int) -> int:
    session = await get_standalone_session()
    async with session:
        rows = (await session.exec(select(WorldLocation).where(WorldLocation.world_id == world_id))).all()
        for row in rows:
            await session.delete(row)
        await session.commit()
        return len(rows)


async def delete(location_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        loc = (await session.exec(select(WorldLocation).where(WorldLocation.id == location_id))).one_or_none()
        if loc is None:
            return False
        await session.delete(loc)
        await session.commit()
        return True
