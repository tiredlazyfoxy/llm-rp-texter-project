"""Embedding service — bridges LLM server config to PythonLLMClient embedding calls."""

import logging
import os

from app.db import llm_servers as db
from app.models.llm_server import LlmServer

logger = logging.getLogger(__name__)


class EmbeddingNotConfiguredError(Exception):
    """Raised when no embedding server is designated."""


# Cached vector dimension (detected from first embedding call)
_cached_dim: int | None = None


def invalidate_cache() -> None:
    """Clear cached embedding dimension. Call when embedding config changes."""
    global _cached_dim
    _cached_dim = None


def _resolve_api_key(raw_key: str | None) -> str | None:
    """Resolve $ENV_VAR syntax to actual value."""
    if raw_key is None:
        return None
    if raw_key.startswith("$"):
        var_name = raw_key[1:]
        value = os.environ.get(var_name)
        if value is None:
            raise EmbeddingNotConfiguredError(
                f"Environment variable '{var_name}' for embedding server API key is not set"
            )
        return value
    return raw_key


def _create_client(server: LlmServer):  # noqa: ANN201
    """Create an LLM client for the embedding server."""
    resolved_key = _resolve_api_key(server.api_key)

    if server.backend_type == "openai":
        from llm import OpenAIAPIClient
        return OpenAIAPIClient(
            model=server.embedding_model or "",
            base_url=server.base_url,
            bearer_token=resolved_key,
        )
    elif server.backend_type == "llama-swap":
        from llm import LlamaSwapAPIClient
        return LlamaSwapAPIClient(
            model=server.embedding_model or "",
            base_url=server.base_url,
            bearer_token=resolved_key,
        )
    else:
        raise EmbeddingNotConfiguredError(
            f"Unsupported backend type for embedding: {server.backend_type}"
        )


async def _get_server() -> LlmServer:
    """Get the designated embedding server or raise."""
    server = await db.get_embedding_server()
    if server is None:
        raise EmbeddingNotConfiguredError("No embedding server configured")
    if not server.embedding_model:
        raise EmbeddingNotConfiguredError("Embedding server has no model configured")
    return server


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using the designated embedding server.

    Raises EmbeddingNotConfiguredError if no embedding server is set up.
    """
    global _cached_dim

    server = await _get_server()
    client = _create_client(server)
    vectors = await client.embed_batch(texts)

    # Cache dimension from first successful call
    if _cached_dim is None and vectors:
        _cached_dim = len(vectors[0])
        logger.info("Embedding dimension detected: %d", _cached_dim)

    return vectors


async def get_vector_dimension() -> int:
    """Return the embedding vector dimension.

    If not cached, performs a test embedding to detect it.
    Raises EmbeddingNotConfiguredError if no server configured.
    """
    global _cached_dim
    if _cached_dim is not None:
        return _cached_dim

    vectors = await embed_texts(["dimension probe"])
    # _cached_dim is set by embed_texts
    assert _cached_dim is not None
    return _cached_dim


async def is_embedding_configured() -> bool:
    """Check if an embedding server is designated (without making API calls)."""
    server = await db.get_embedding_server()
    return server is not None and bool(server.embedding_model)
