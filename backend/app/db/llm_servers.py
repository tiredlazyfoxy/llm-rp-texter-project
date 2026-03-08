"""LLM server data access. Session-free public API — all sessions managed internally."""

from sqlalchemy import update as sa_update
from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.llm_server import LlmServer


async def get_by_id(server_id: int) -> LlmServer | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(LlmServer).where(LlmServer.id == server_id))).one_or_none()


async def get_all() -> list[LlmServer]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(select(LlmServer).order_by(LlmServer.name))).all())


async def get_active() -> list[LlmServer]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(
            select(LlmServer).where(LlmServer.is_active == True).order_by(LlmServer.name)  # noqa: E712
        )).all())


async def create(server: LlmServer) -> LlmServer:
    session = await get_standalone_session()
    async with session:
        session.add(server)
        await session.commit()
        await session.refresh(server)
        return server


async def update(server: LlmServer) -> None:
    session = await get_standalone_session()
    async with session:
        session.add(server)
        await session.commit()
        await session.refresh(server)


async def clear_all_embedding() -> None:
    """Set is_embedding=False and embedding_model=None on ALL servers."""
    session = await get_standalone_session()
    async with session:
        await session.execute(
            sa_update(LlmServer).values(is_embedding=False, embedding_model=None)
        )
        await session.commit()


async def delete(server_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        server = (await session.exec(select(LlmServer).where(LlmServer.id == server_id))).one_or_none()
        if server is None:
            return False
        await session.delete(server)
        await session.commit()
        return True
