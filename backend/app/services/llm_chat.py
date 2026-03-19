"""LLM chat service — client factory for model-based routing."""

import json
import logging
import os

from fastapi import HTTPException, status
from llm import LLMClient, LlamaSwapAPIClient, OpenAIAPIClient

from app.db import llm_servers as db

logger = logging.getLogger(__name__)


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


async def get_llm_client_for_model(model_id: str) -> LLMClient:
    """Find the first active server that has *model_id* enabled and return a client."""
    servers = await db.get_active()
    for server in servers:
        models: list[str] = json.loads(server.enabled_models) if server.enabled_models else []
        if model_id not in models:
            continue

        resolved_key = _resolve_api_key(server.api_key)

        if server.backend_type == "openai":
            return OpenAIAPIClient(
                model=model_id, base_url=server.base_url, bearer_token=resolved_key,
            )
        if server.backend_type == "llama-swap":
            return LlamaSwapAPIClient(
                model=model_id, base_url=server.base_url, bearer_token=resolved_key,
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported backend type: {server.backend_type}",
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No active server has model '{model_id}' enabled",
    )
