"""Admin DB management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response

from app.models.schemas.db_management import (
    ColumnInfoSchema,
    DbStatusResponse,
    ReindexResultSchema,
    SyncResultSchema,
    TableStatusSchema,
)
from app.models.user import User, UserRole
from app.services import db_import_export
from app.services import db_management as db_mgmt_service
from app.services import vector_storage
from app.services.auth import require_role
from app.services.embedding import EmbeddingNotConfiguredError

_require_admin = require_role(UserRole.admin)

router = APIRouter(prefix="/api/admin/db", tags=["admin-db"])


@router.get("", response_model=DbStatusResponse)
async def get_db_status(
    _caller: User = Depends(_require_admin),
) -> DbStatusResponse:
    statuses = await db_mgmt_service.get_db_status()
    return DbStatusResponse(
        tables=[
            TableStatusSchema(
                class_name=s["class_name"],
                table_name=s["table_name"],
                table_exists=s["table_exists"],
                record_count=s["record_count"],
                schema_status=s["schema_status"],
                columns_in_model=[ColumnInfoSchema(**f) for f in s["columns_in_model"]],
                table_columns=[ColumnInfoSchema(**c) for c in s["table_columns"]],
                missing_columns=s["missing_columns"],
                extra_columns=s["extra_columns"],
            )
            for s in statuses
        ]
    )


@router.post(
    "/tables/{table_name}/create",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def create_table(
    table_name: str,
    _caller: User = Depends(_require_admin),
) -> None:
    try:
        await db_mgmt_service.create_missing_table(table_name)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown table: {table_name}",
        )


@router.post("/tables/{table_name}/sync", response_model=SyncResultSchema)
async def sync_table(
    table_name: str,
    _caller: User = Depends(_require_admin),
) -> SyncResultSchema:
    try:
        result = await db_mgmt_service.sync_table_schema(table_name)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown table: {table_name}",
        )
    return SyncResultSchema(
        added_columns=result["added_columns"],
        dropped_columns=result["dropped_columns"],
    )


@router.get("/export")
async def export_db(
    _caller: User = Depends(_require_admin),
) -> Response:
    zip_bytes = await db_import_export.export_all()
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=llmrp_export.zip"},
    )


@router.post("/import", status_code=status.HTTP_204_NO_CONTENT)
async def import_db(
    file: UploadFile,
    _caller: User = Depends(_require_admin),
) -> None:
    zip_data = await file.read()
    await db_import_export.import_all(zip_data)


@router.post("/reindex-vectors", response_model=ReindexResultSchema)
async def reindex_vectors(
    _caller: User = Depends(_require_admin),
) -> ReindexResultSchema:
    """Rebuild vector index for all world documents using the configured embedding server."""
    try:
        doc_count = await vector_storage.rebuild_all_worlds_index()
        return ReindexResultSchema(success=True, documents_indexed=doc_count)
    except EmbeddingNotConfiguredError as e:
        return ReindexResultSchema(success=False, documents_indexed=0, error=str(e))
