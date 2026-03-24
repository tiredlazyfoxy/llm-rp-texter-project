"""DB introspection queries — table list, columns, counts, create.

Session-free public API. All functions manage their own sessions/engine
access internally.
"""

import logging
from typing import TypedDict

from sqlalchemy import Column as SaColumn, MetaData, Table, text

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


async def recreate_table_from_model(table_obj: Table, keep_columns: list[str]) -> None:
    """Recreate a table from its model definition, keeping only listed columns' data.

    Uses the SQLite 12-step recreation pattern:
    1. Disable foreign keys
    2. Create new table from model schema (with proper types, FKs, indexes)
    3. Copy data for overlapping columns
    4. Drop old table
    5. Rename new table
    6. Re-enable foreign keys
    """
    from app.db.engine import _engine

    if _engine is None:
        raise RuntimeError("Database engine not initialized")

    table_name = table_obj.name
    tmp_name = f"_tmp_rebuild_{table_name}"

    # Build a temporary Table object with the tmp name but same schema
    tmp_meta = MetaData()
    tmp_table = Table(
        tmp_name, tmp_meta,
        *(SaColumn(c.name, c.type, primary_key=c.primary_key, nullable=c.nullable)
          for c in table_obj.columns),
    )

    cols_csv = ", ".join(f"[{c}]" for c in keep_columns)

    async with _engine.connect() as conn:
        await conn.execute(text("PRAGMA foreign_keys = OFF"))
        # Create temp table with proper schema
        await conn.run_sync(tmp_table.create)
        # Copy data for columns that exist in both old and new
        await conn.execute(text(
            f"INSERT INTO [{tmp_name}] ({cols_csv}) SELECT {cols_csv} FROM [{table_name}]"
        ))
        await conn.execute(text(f"DROP TABLE [{table_name}]"))
        await conn.execute(text(f"ALTER TABLE [{tmp_name}] RENAME TO [{table_name}]"))
        await conn.commit()
        await conn.execute(text("PRAGMA foreign_keys = ON"))

    logger.info("Recreated table %s (kept columns: %s)", table_name, keep_columns)
