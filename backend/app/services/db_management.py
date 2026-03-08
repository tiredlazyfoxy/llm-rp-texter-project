"""DB management service — introspection, schema drift detection, table creation."""

import logging
from typing import TypedDict

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


def _get_model_columns(model_class: type) -> list[ColumnInfo]:
    """Extract column names and types from a SQLModel class."""
    table = model_class.__table__  # type: ignore[attr-defined]
    return [
        ColumnInfo(name=col.name, type=str(col.type))
        for col in table.columns
    ]


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
    for reg_table_name, model_class, _, _ in TABLE_REGISTRY:
        if reg_table_name == table_name:
            table_obj = model_class.__table__  # type: ignore[attr-defined]
            await db_mgmt.create_single_table(table_obj)
            logger.info("Created table %s for model %s", table_name, model_class.__name__)
            return

    raise ValueError(f"Unknown table: {table_name}")
