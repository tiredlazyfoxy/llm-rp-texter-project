"""Pydantic schemas for DB management API."""

from pydantic import BaseModel


class ColumnInfoSchema(BaseModel):
    name: str
    type: str


class TableStatusSchema(BaseModel):
    class_name: str
    table_name: str
    table_exists: bool
    record_count: int | None
    schema_status: str  # "ok" | "drift" | "missing"
    columns_in_model: list[ColumnInfoSchema]
    table_columns: list[ColumnInfoSchema]
    missing_columns: list[str]
    extra_columns: list[str]


class DbStatusResponse(BaseModel):
    tables: list[TableStatusSchema]
