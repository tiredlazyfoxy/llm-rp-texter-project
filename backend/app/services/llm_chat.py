"""LLM chat service — client factory for model-based routing."""

import asyncio
import json
import logging
import os
from collections.abc import AsyncGenerator

from fastapi import HTTPException, status
from llm import LLMClient, LlamaSwapAPIClient, OpenAIAPIClient
from llm.message import LLMMessage

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


_TRANSLATE_SYSTEM_BASE = (
    "You are a translator. Translate the user's message into English. "
    "Output ONLY the translated text, nothing else. "
    "If the text is already in English, return it unchanged."
)


def _translate_system(enable_thinking: bool) -> str:
    if enable_thinking:
        return _TRANSLATE_SYSTEM_BASE
    return "/no_think\n" + _TRANSLATE_SYSTEM_BASE


def _sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def translate_to_english_stream(
    text: str,
    model_id: str,
    *,
    temperature: float = 0.1,
    top_p: float = 1.0,
    repeat_penalty: float = 1.0,
    enable_thinking: bool = False,
) -> AsyncGenerator[str, None]:
    """Translate text to English, yielding SSE events (token + done)."""
    client = await get_llm_client_for_model(model_id)
    messages: list[LLMMessage] = [{"role": "user", "content": text}]
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    content_parts: list[str] = []
    in_thinking = False

    async def on_delta(delta: str) -> None:
        nonlocal in_thinking
        text = delta

        # Stream thinking tokens so UI can show progress, but don't
        # include them in content_parts (done event = clean translation only)
        if not in_thinking and "<think>" in text:
            idx = text.index("<think>")
            before = text[:idx]
            after = text[idx + 7:]
            if before:
                content_parts.append(before)
                await queue.put(_sse("token", {"content": before}))
            in_thinking = True
            if after:
                await queue.put(_sse("thinking", {"content": after}))
            return

        if in_thinking and "</think>" in text:
            idx = text.index("</think>")
            before = text[:idx]
            after = text[idx + 8:]
            if before:
                await queue.put(_sse("thinking", {"content": before}))
            in_thinking = False
            if after:
                content_parts.append(after)
                await queue.put(_sse("token", {"content": after}))
            return

        if in_thinking:
            await queue.put(_sse("thinking", {"content": text}))
            return

        content_parts.append(text)
        await queue.put(_sse("token", {"content": text}))

    async def run_llm() -> None:
        try:
            async with client:
                await client.chat(
                    messages,
                    system=_translate_system(enable_thinking),
                    options={
                        "temperature": temperature,
                        "top_p": top_p,
                        "repeat_penalty": repeat_penalty,
                        "enable_thinking": enable_thinking,
                    },
                    stream=True,
                    on_delta=on_delta,
                )
            full = "".join(content_parts).strip()
            await queue.put(_sse("done", {"content": full}))
        except Exception as exc:
            logger.exception("Translation stream error")
            await queue.put(_sse("error", {"message": str(exc)}))
        finally:
            await queue.put(None)

    task = asyncio.create_task(run_llm())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        if not task.done():
            task.cancel()
