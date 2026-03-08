"""World lore fact data access. Session-free public API."""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.world import WorldLoreFact


async def get_by_id(fact_id: int) -> WorldLoreFact | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(WorldLoreFact).where(WorldLoreFact.id == fact_id))).one_or_none()


async def list_by_world(world_id: int) -> list[WorldLoreFact]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(select(WorldLoreFact).where(WorldLoreFact.world_id == world_id))).all())


async def create(fact: WorldLoreFact) -> WorldLoreFact:
    session = await get_standalone_session()
    async with session:
        session.add(fact)
        await session.commit()
        await session.refresh(fact)
        return fact


async def update(fact: WorldLoreFact) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(fact)
        await session.commit()


async def delete(fact_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        fact = (await session.exec(select(WorldLoreFact).where(WorldLoreFact.id == fact_id))).one_or_none()
        if fact is None:
            return False
        await session.delete(fact)
        await session.commit()
        return True
