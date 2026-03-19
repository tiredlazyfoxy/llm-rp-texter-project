"""Admin LLM server management endpoints."""

import json

from fastapi import APIRouter, Depends, status

from app.models.llm_server import LlmServer
from app.models.schemas.llm_servers import (
    AvailableModelsResponse,
    CreateLlmServerRequest,
    EmbeddingConfigResponse,
    EnabledModelsRequest,
    LlmServerResponse,
    LlmServersListResponse,
    SetEmbeddingRequest,
    UpdateLlmServerRequest,
)
from app.models.user import User, UserRole
from app.services import llm_servers as llm_service
from app.services.auth import require_role

_require_admin = require_role(UserRole.admin)

router = APIRouter(prefix="/api/admin/llm-servers", tags=["admin-llm-servers"])


def _to_response(server: LlmServer) -> LlmServerResponse:
    return LlmServerResponse(
        id=str(server.id),
        name=server.name,
        backend_type=server.backend_type,
        base_url=server.base_url,
        has_api_key=server.api_key is not None and server.api_key != "",
        enabled_models=json.loads(server.enabled_models),
        is_active=server.is_active,
        is_embedding=server.is_embedding,
        embedding_model=server.embedding_model,
        created_at=server.created_at,
        modified_at=server.modified_at,
    )


@router.get("", response_model=LlmServersListResponse)
async def list_servers(
    _caller: User = Depends(_require_admin),
) -> LlmServersListResponse:
    servers = await llm_service.get_all_servers()
    return LlmServersListResponse(items=[_to_response(s) for s in servers])


@router.post("", response_model=LlmServerResponse, status_code=status.HTTP_201_CREATED)
async def create_server(
    body: CreateLlmServerRequest,
    _caller: User = Depends(_require_admin),
) -> LlmServerResponse:
    server = await llm_service.create_server(body)
    return _to_response(server)


# --- Static paths before /{server_id} to avoid path param conflicts ---


@router.get("/embedding", response_model=EmbeddingConfigResponse)
async def get_embedding_config(
    _caller: User = Depends(_require_admin),
) -> EmbeddingConfigResponse:
    return await llm_service.get_embedding_config()


@router.delete("/embedding", status_code=status.HTTP_204_NO_CONTENT)
async def clear_embedding(
    _caller: User = Depends(_require_admin),
) -> None:
    await llm_service.clear_embedding_server()


# --- Routes with {server_id} path parameter ---


@router.put("/{server_id}", response_model=LlmServerResponse)
async def update_server(
    server_id: str,
    body: UpdateLlmServerRequest,
    _caller: User = Depends(_require_admin),
) -> LlmServerResponse:
    server = await llm_service.update_server(int(server_id), body)
    return _to_response(server)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: str,
    _caller: User = Depends(_require_admin),
) -> None:
    await llm_service.delete_server(int(server_id))


@router.get("/{server_id}/available-models", response_model=AvailableModelsResponse)
async def probe_available_models(
    server_id: str,
    _caller: User = Depends(_require_admin),
) -> AvailableModelsResponse:
    models = await llm_service.probe_models(int(server_id))
    return AvailableModelsResponse(models=models)


@router.put("/{server_id}/enabled-models", response_model=LlmServerResponse)
async def set_enabled_models(
    server_id: str,
    body: EnabledModelsRequest,
    _caller: User = Depends(_require_admin),
) -> LlmServerResponse:
    server = await llm_service.set_enabled_models(int(server_id), body.enabled_models)
    return _to_response(server)


@router.put("/{server_id}/embedding", response_model=LlmServerResponse)
async def set_embedding(
    server_id: str,
    body: SetEmbeddingRequest,
    _caller: User = Depends(_require_admin),
) -> LlmServerResponse:
    server = await llm_service.set_embedding_server(int(server_id), body.model)
    return _to_response(server)
