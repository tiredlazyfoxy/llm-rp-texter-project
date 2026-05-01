"""Pipeline data access. Session-free public API — all sessions managed internally."""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.pipeline import Pipeline
from app.models.world import World


async def get_by_id(pipeline_id: int) -> Pipeline | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(Pipeline).where(Pipeline.id == pipeline_id))).one_or_none()


async def list_all() -> list[Pipeline]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(select(Pipeline))).all())


async def create(pipeline: Pipeline) -> Pipeline:
    session = await get_standalone_session()
    async with session:
        session.add(pipeline)
        await session.commit()
        await session.refresh(pipeline)
        return pipeline


async def update(pipeline: Pipeline) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(pipeline)
        await session.commit()


async def delete(pipeline_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        pipeline = (await session.exec(select(Pipeline).where(Pipeline.id == pipeline_id))).one_or_none()
        if pipeline is None:
            return False
        await session.delete(pipeline)
        await session.commit()
        return True


async def is_referenced(pipeline_id: int) -> bool:
    """Return True if any World references this pipeline via pipeline_id."""
    session = await get_standalone_session()
    async with session:
        row = (await session.exec(
            select(World.id).where(World.pipeline_id == pipeline_id).limit(1)
        )).first()
        return row is not None
