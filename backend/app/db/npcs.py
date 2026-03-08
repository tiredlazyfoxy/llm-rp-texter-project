"""World NPC data access. Session-free public API."""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.world import WorldNPC


async def get_by_id(npc_id: int) -> WorldNPC | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(WorldNPC).where(WorldNPC.id == npc_id))).one_or_none()


async def list_by_world(world_id: int) -> list[WorldNPC]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(select(WorldNPC).where(WorldNPC.world_id == world_id))).all())


async def create(npc: WorldNPC) -> WorldNPC:
    session = await get_standalone_session()
    async with session:
        session.add(npc)
        await session.commit()
        await session.refresh(npc)
        return npc


async def update(npc: WorldNPC) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(npc)
        await session.commit()


async def delete(npc_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        npc = (await session.exec(select(WorldNPC).where(WorldNPC.id == npc_id))).one_or_none()
        if npc is None:
            return False
        await session.delete(npc)
        await session.commit()
        return True
