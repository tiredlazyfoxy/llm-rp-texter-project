"""DB management service — introspection, schema drift detection, table creation, sync."""

import logging
from typing import TypedDict

from sqlalchemy import Column

from app.db import db_management as db_mgmt
from app.services.db_import_export import TABLE_REGISTRY

logger = logging.getLogger(__name__)


class ColumnInfo(TypedDict):
    name: str
    type: str


class TableStatusInfo(TypedDict):
    class_name: str
    table_name: str
    table_exists: bool
    record_count: int | None
    schema_status: str  # "ok" | "drift" | "missing"
    columns_in_model: list[ColumnInfo]
    table_columns: list[ColumnInfo]
    missing_columns: list[str]
    extra_columns: list[str]


class SyncResultInfo(TypedDict):
    added_columns: list[str]
    dropped_columns: list[str]


def _find_model(table_name: str) -> type:
    """Look up a model class by its table name in the registry."""
    for reg_table_name, model_class, _, _ in TABLE_REGISTRY:
        if reg_table_name == table_name:
            return model_class
    raise ValueError(f"Unknown table: {table_name}")


def _get_model_columns(model_class: type) -> list[ColumnInfo]:
    """Extract column names and types from a SQLModel class."""
    table = model_class.__table__  # type: ignore[attr-defined]
    return [
        ColumnInfo(name=col.name, type=str(col.type))
        for col in table.columns
    ]


def _build_column_ddl(col: Column) -> str:  # type: ignore[type-arg]
    """Build the DDL fragment for ALTER TABLE ADD COLUMN from a SQLAlchemy Column."""
    type_str = str(col.type)

    # Determine default value
    default_clause = ""
    if col.default is not None and col.default.arg is not None and not callable(col.default.arg):
        val = col.default.arg
        if isinstance(val, str):
            escaped = val.replace("'", "''")
            default_clause = f" DEFAULT '{escaped}'"
        elif isinstance(val, bool):
            default_clause = f" DEFAULT {1 if val else 0}"
        elif isinstance(val, (int, float)):
            default_clause = f" DEFAULT {val}"
    elif not col.nullable:
        # NOT NULL without a default — provide type-appropriate zero value
        upper = type_str.upper()
        if "INT" in upper or "BOOL" in upper:
            default_clause = " DEFAULT 0"
        else:
            default_clause = " DEFAULT ''"

    return f"{type_str}{default_clause}"


async def get_db_status() -> list[TableStatusInfo]:
    """Get status of all registered model tables."""
    existing_tables = set(await db_mgmt.get_existing_tables())

    results: list[TableStatusInfo] = []
    for table_name, model_class, _, _ in TABLE_REGISTRY:
        class_name = model_class.__name__
        columns_in_model = _get_model_columns(model_class)
        model_field_names = {f["name"] for f in columns_in_model}

        if table_name not in existing_tables:
            results.append(TableStatusInfo(
                class_name=class_name,
                table_name=table_name,
                table_exists=False,
                record_count=None,
                schema_status="missing",
                columns_in_model=columns_in_model,
                table_columns=[],
                missing_columns=sorted(model_field_names),
                extra_columns=[],
            ))
            continue

        table_columns = await db_mgmt.get_table_columns(table_name)
        table_col_names = {c["name"] for c in table_columns}
        record_count = await db_mgmt.get_record_count(table_name)

        missing = sorted(model_field_names - table_col_names)
        extra = sorted(table_col_names - model_field_names)
        schema_status = "drift" if missing or extra else "ok"

        results.append(TableStatusInfo(
            class_name=class_name,
            table_name=table_name,
            table_exists=True,
            record_count=record_count,
            schema_status=schema_status,
            columns_in_model=columns_in_model,
            table_columns=table_columns,
            missing_columns=missing,
            extra_columns=extra,
        ))

    return results


async def create_missing_table(table_name: str) -> None:
    """Create a missing table by its registered table name."""
    model_class = _find_model(table_name)
    table_obj = model_class.__table__  # type: ignore[attr-defined]
    await db_mgmt.create_single_table(table_obj)
    logger.info("Created table %s for model %s", table_name, model_class.__name__)


async def sync_table_schema(table_name: str) -> SyncResultInfo:
    """Add missing columns and drop extra columns to match the model."""
    model_class = _find_model(table_name)

    # Get current DB columns
    table_columns = await db_mgmt.get_table_columns(table_name)
    existing_col_names = {c["name"] for c in table_columns}

    # Get model columns from SQLAlchemy
    sa_table = model_class.__table__  # type: ignore[attr-defined]
    model_col_names = {col.name for col in sa_table.columns}

    # Add missing columns
    added: list[str] = []
    for col in sa_table.columns:
        if col.name not in existing_col_names:
            ddl = _build_column_ddl(col)
            await db_mgmt.add_column(table_name, col.name, ddl)
            added.append(col.name)

    # Drop extra columns
    dropped: list[str] = []
    for col_name in sorted(existing_col_names - model_col_names):
        await db_mgmt.drop_column(table_name, col_name)
        dropped.append(col_name)

    logger.info(
        "Synced table %s: added %s, dropped %s",
        table_name, added, dropped,
    )
    return SyncResultInfo(added_columns=added, dropped_columns=dropped)
