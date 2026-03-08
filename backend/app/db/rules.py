"""World rule data access. Session-free public API."""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.world import WorldRule


async def get_by_id(rule_id: int) -> WorldRule | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(WorldRule).where(WorldRule.id == rule_id))).one_or_none()


async def list_by_world(world_id: int) -> list[WorldRule]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(
            select(WorldRule).where(WorldRule.world_id == world_id).order_by(WorldRule.order)
        )).all())


async def create(rule: WorldRule) -> WorldRule:
    session = await get_standalone_session()
    async with session:
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule


async def update(rule: WorldRule) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(rule)
        await session.commit()


async def delete(rule_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        rule = (await session.exec(select(WorldRule).where(WorldRule.id == rule_id))).one_or_none()
        if rule is None:
            return False
        await session.delete(rule)
        await session.commit()
        return True
