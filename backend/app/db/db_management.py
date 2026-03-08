"""DB introspection queries — table list, columns, counts, create.

Session-free public API. All functions manage their own sessions/engine
access internally.
"""

import logging
from typing import TypedDict

from sqlalchemy import Table, text

logger = logging.getLogger(__name__)


class ColumnInfo(TypedDict):
    name: str
    type: str


async def get_existing_tables() -> list[str]:
    """Return names of all user tables in the SQLite database."""
    from app.db.engine import get_standalone_session

    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        )
        return [row[0] for row in result.all()]


async def get_table_columns(table_name: str) -> list[ColumnInfo]:
    """Return column info for a table via PRAGMA table_info."""
    from app.db.engine import get_standalone_session

    session = await get_standalone_session()
    async with session:
        result = await session.exec(text(f"PRAGMA table_info('{table_name}')"))
        return [
            ColumnInfo(name=row[1], type=row[2])
            for row in result.all()
        ]


async def get_record_count(table_name: str) -> int:
    """Return the number of rows in a table."""
    from app.db.engine import get_standalone_session

    session = await get_standalone_session()
    async with session:
        result = await session.exec(text(f"SELECT COUNT(*) FROM '{table_name}'"))
        return result.one()[0]


async def create_single_table(table_obj: Table) -> None:
    """Create a single table using its SQLAlchemy Table object."""
    from app.db.engine import _engine

    if _engine is None:
        raise RuntimeError("Database engine not initialized")

    async with _engine.begin() as conn:
        await conn.run_sync(table_obj.create, checkfirst=True)


async def add_column(table_name: str, col_name: str, col_ddl: str) -> None:
    """Add a column to an existing table via ALTER TABLE ADD COLUMN."""
    from app.db.engine import _engine

    if _engine is None:
        raise RuntimeError("Database engine not initialized")

    async with _engine.begin() as conn:
        await conn.execute(
            text(f"ALTER TABLE [{table_name}] ADD COLUMN [{col_name}] {col_ddl}")
        )
    logger.info("Added column %s to table %s", col_name, table_name)


async def drop_column(table_name: str, col_name: str) -> None:
    """Drop a column from an existing table via ALTER TABLE DROP COLUMN."""
    from app.db.engine import _engine

    if _engine is None:
        raise RuntimeError("Database engine not initialized")

    async with _engine.begin() as conn:
        await conn.execute(
            text(f"ALTER TABLE [{table_name}] DROP COLUMN [{col_name}]")
        )
    logger.info("Dropped column %s from table %s", col_name, table_name)
