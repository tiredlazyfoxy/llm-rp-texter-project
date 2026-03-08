"""World data access. Session-free public API — all sessions managed internally."""

from sqlalchemy import or_
from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.world import World, WorldStatus


async def get_by_id(world_id: int) -> World | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(World).where(World.id == world_id))).one_or_none()


async def list_all() -> list[World]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(select(World))).all())


async def list_for_user(user_id: int) -> list[World]:
    """List worlds visible to a non-admin user: excludes others' private worlds."""
    session = await get_standalone_session()
    async with session:
        q = select(World).where(
            or_(
                World.status != WorldStatus.private,  # type: ignore[arg-type]
                World.owner_id == user_id,  # type: ignore[arg-type]
                World.owner_id.is_(None),  # type: ignore[union-attr]
            )
        )
        return list((await session.exec(q)).all())


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
