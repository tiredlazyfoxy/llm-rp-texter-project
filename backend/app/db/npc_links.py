"""NPC-location link data access. Session-free public API."""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.world import NPCLocationLink, WorldNPC


async def get_by_id(link_id: int) -> NPCLocationLink | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(NPCLocationLink).where(NPCLocationLink.id == link_id))).one_or_none()


async def list_by_npc(npc_id: int) -> list[NPCLocationLink]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(select(NPCLocationLink).where(NPCLocationLink.npc_id == npc_id))).all())


async def list_by_location(location_id: int) -> list[NPCLocationLink]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(
            select(NPCLocationLink).where(NPCLocationLink.location_id == location_id)
        )).all())


async def list_by_world(world_id: int) -> list[NPCLocationLink]:
    session = await get_standalone_session()
    async with session:
        npc_ids_q = select(WorldNPC.id).where(WorldNPC.world_id == world_id)
        return list((await session.exec(
            select(NPCLocationLink).where(NPCLocationLink.npc_id.in_(npc_ids_q))  # type: ignore[union-attr]
        )).all())


async def delete_by_world(world_id: int) -> int:
    session = await get_standalone_session()
    async with session:
        npc_ids_q = select(WorldNPC.id).where(WorldNPC.world_id == world_id)
        rows = (await session.exec(
            select(NPCLocationLink).where(NPCLocationLink.npc_id.in_(npc_ids_q))  # type: ignore[union-attr]
        )).all()
        for row in rows:
            await session.delete(row)
        await session.commit()
        return len(rows)


async def delete_by_npc(npc_id: int) -> int:
    session = await get_standalone_session()
    async with session:
        rows = (await session.exec(select(NPCLocationLink).where(NPCLocationLink.npc_id == npc_id))).all()
        for row in rows:
            await session.delete(row)
        await session.commit()
        return len(rows)


async def create(link: NPCLocationLink) -> NPCLocationLink:
    session = await get_standalone_session()
    async with session:
        session.add(link)
        await session.commit()
        await session.refresh(link)
        return link


async def delete(link_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        link = (await session.exec(select(NPCLocationLink).where(NPCLocationLink.id == link_id))).one_or_none()
        if link is None:
            return False
        await session.delete(link)
        await session.commit()
        return True
