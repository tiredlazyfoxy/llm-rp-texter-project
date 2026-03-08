"""LLM server management — business logic for CRUD, model probing, and model selection."""

import json
import logging
import os
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.db import llm_servers as db
from app.models.llm_server import LlmServer
from app.models.schemas.llm_servers import (
    CreateLlmServerRequest,
    EnabledModelInfo,
    UpdateLlmServerRequest,
)
from app.services.snowflake import generate_id

logger = logging.getLogger(__name__)

_VALID_BACKEND_TYPES = {"llama-swap", "openai"}


def _strip_url(url: str) -> str:
    return url.rstrip("/")


def _resolve_api_key(raw_key: str | None) -> str | None:
    """Resolve $ENV_VAR syntax to actual value."""
    if raw_key is None:
        return None
    if raw_key.startswith("$"):
        var_name = raw_key[1:]
        value = os.environ.get(var_name)
        if value is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Environment variable '{var_name}' is not set",
            )
        return value
    return raw_key


async def get_all_servers() -> list[LlmServer]:
    return await db.get_all()


def _validate_backend_type(backend_type: str) -> None:
    if backend_type not in _VALID_BACKEND_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid backend_type: {backend_type}. Must be one of: {', '.join(sorted(_VALID_BACKEND_TYPES))}",
        )


async def create_server(req: CreateLlmServerRequest) -> LlmServer:
    _validate_backend_type(req.backend_type)
    now = datetime.now(timezone.utc)
    server = LlmServer(
        id=generate_id(),
        name=req.name,
        backend_type=req.backend_type,
        base_url=_strip_url(req.base_url),
        api_key=req.api_key,
        is_active=req.is_active,
        created_at=now,
        modified_at=now,
    )
    return await db.create(server)


async def update_server(server_id: int, req: UpdateLlmServerRequest) -> LlmServer:
    server = await db.get_by_id(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    if req.name is not None:
        server.name = req.name
    if req.backend_type is not None:
        _validate_backend_type(req.backend_type)
        server.backend_type = req.backend_type
    if req.base_url is not None:
        server.base_url = _strip_url(req.base_url)
    if req.api_key is not None:
        server.api_key = req.api_key if req.api_key != "" else None
    if req.is_active is not None:
        server.is_active = req.is_active

    server.modified_at = datetime.now(timezone.utc)
    await db.update(server)
    return server


async def delete_server(server_id: int) -> None:
    deleted = await db.delete(server_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")


async def probe_models(server_id: int) -> list[str]:
    """Probe a server for available models via its API."""
    server = await db.get_by_id(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    resolved_key = _resolve_api_key(server.api_key)

    try:
        if server.backend_type == "openai":
            from llm import OpenAIAPIClient
            client = OpenAIAPIClient(model="", base_url=server.base_url, bearer_token=resolved_key)
        elif server.backend_type == "llama-swap":
            from llm import LlamaSwapAPIClient
            client = LlamaSwapAPIClient(model="", base_url=server.base_url, bearer_token=resolved_key)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported backend type: {server.backend_type}",
            )

        models = await client.list_models()
        return sorted(models)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Failed to probe server %s (%s): %s", server.name, server.base_url, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to connect to server: {e}",
        )


async def set_enabled_models(server_id: int, models: list[str]) -> LlmServer:
    server = await db.get_by_id(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    server.enabled_models = json.dumps(models)
    server.modified_at = datetime.now(timezone.utc)
    await db.update(server)
    return server


async def get_all_enabled_models() -> list[EnabledModelInfo]:
    """Get all enabled models across all active servers (for editor model picker)."""
    servers = await db.get_active()
    result: list[EnabledModelInfo] = []
    for server in servers:
        models = json.loads(server.enabled_models)
        for model_id in models:
            result.append(EnabledModelInfo(
                server_id=str(server.id),
                server_name=server.name,
                model_id=model_id,
            ))
    return result
