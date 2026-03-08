"""DB-layer import/export operations. Session-free public API.

All functions manage their own sessions internally — callers never touch
AsyncSession, select(), or any ORM primitives.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlmodel import SQLModel, select

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=SQLModel)


async def export_table(
    model_class: type[T],
    callback: Callable[[T], None | Awaitable[None]],
) -> None:
    """Iterate all rows of a table, calling callback(row) for each.

    Session is opened and closed internally. Callback receives detached
    model instances suitable for serialization.
    """
    from app.db.engine import get_standalone_session

    session = await get_standalone_session()
    async with session:
        results = (await session.exec(select(model_class))).all()
        for row in results:
            result = callback(row)
            if result is not None:
                await result


async def upsert_batch(items: list[SQLModel]) -> None:
    """Upsert (merge) a batch of model instances into the database.

    Uses session.merge() for each item — inserts new rows, updates existing
    ones by primary key. Commits the batch. Session managed internally.
    """
    if not items:
        return

    from app.db.engine import get_standalone_session

    session = await get_standalone_session()
    async with session:
        for item in items:
            await session.merge(item)
        await session.commit()


async def run_vector_rebuild() -> None:
    """Rebuild vector indices from DB documents."""
    from app.services.vector_storage import rebuild_all_worlds_index

    await rebuild_all_worlds_index()
