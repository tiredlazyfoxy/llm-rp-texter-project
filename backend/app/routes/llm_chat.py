"""LLM chat route — SSE streaming endpoint for the document editor."""

import asyncio
import functools
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.responses import StreamingResponse

from app.db import lore_facts as lore_facts_db
from app.db import worlds as worlds_db
from app.models.schemas.llm_chat import LlmChatRequest, TranslateRequest
from app.models.user import User, UserRole
from llm.message import LLMMessage

from app.services.auth import require_role
from app.services import llm_chat as llm_chat_service
from app.services.llm_chat import get_llm_client_for_model
from app.services.prompts import (
    build_document_editor_system,
    build_pipeline_prompt_editor_system,
    build_world_field_editor_system,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/llm", tags=["llm"])

_require_editor = require_role(UserRole.editor)


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def _run_with_tools(
    client,
    messages: list[LLMMessage],
    system_prompt: str,
    options: dict,
    queue: asyncio.Queue,
    content_parts: list[str],
    world_id: int | None,
    world_agnostic: bool = False,
) -> None:
    """Tool-enabled agentic loop: wraps each tool to emit SSE events, then calls chat_with_tools.

    When ``world_agnostic`` is True (pipeline-prompt editor), only world-agnostic
    tools (``web_search``) are exposed and ``world_id`` is ignored.
    """
    from app.services.admin_tools import (
        ADMIN_TOOL_DEFINITIONS,
        WORLD_AGNOSTIC_TOOL_DEFINITIONS,
        get_admin_tools,
        get_world_agnostic_tools,
    )

    if world_agnostic or world_id is None:
        base_tools = get_world_agnostic_tools()
        tool_definitions = WORLD_AGNOSTIC_TOOL_DEFINITIONS
    else:
        base_tools = get_admin_tools(world_id)
        tool_definitions = ADMIN_TOOL_DEFINITIONS

    def _make_wrapper(name: str, impl):
        @functools.wraps(impl)
        async def wrapper(**kwargs):
            await queue.put(_sse_event("tool_call_start", {"tool_name": name, "arguments": kwargs}))
            result = await impl(**kwargs)
            await queue.put(_sse_event("tool_call_result", {"tool_name": name, "result": result}))
            return result
        return wrapper

    tools = {name: _make_wrapper(name, fn) for name, fn in base_tools.items()}

    # chat_with_tools doesn't support enable_thinking — strip it
    tools_options = {k: v for k, v in options.items() if k != "enable_thinking"}

    async def on_delta(delta: str) -> None:
        content_parts.append(delta)
        await queue.put(_sse_event("token", {"content": delta}))

    async with client:
        await client.chat_with_tools(
            messages,
            tools_definitions=tool_definitions,
            tools=tools,
            system=system_prompt,
            options=tools_options,
            max_loops=15,
            stream=True,
            on_delta=on_delta,
        )

    full_content = "".join(content_parts)
    await queue.put(_sse_event("done", {"content": full_content}))


@router.post("/chat")
async def chat_stream(
    req: LlmChatRequest,
    _caller: User = Depends(_require_editor),
) -> StreamingResponse:
    # Pipeline-prompt editor is world-agnostic: pipelines are shared across worlds,
    # so the helper must not pull world name / lore / NPCs into the prompt or its tools.
    is_pipeline_prompt = req.field_type == "pipeline_prompt"

    if is_pipeline_prompt:
        system_prompt = build_pipeline_prompt_editor_system(
            current_content=req.current_content,
            enable_tools=req.enable_tools,
        )
        world_id_int: int | None = None
    else:
        # Load world context
        if not req.world_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="world_id is required for world-scoped chat",
            )
        world_id_int = int(req.world_id)
        world = await worlds_db.get_by_id(world_id_int)
        if world is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")

        # is_injected lore facts are always included in the system prompt (even with tools enabled)
        injected_facts = await lore_facts_db.list_injected_by_world(world_id_int)
        injected_lore = "\n\n".join(f.content for f in injected_facts if f.content)

        # When tools are enabled, the LLM fetches non-injected lore actively via search/get_lore.
        # Without tools, inject all non-injected facts too.
        if req.enable_tools:
            world_lore = ""
        else:
            all_facts = await lore_facts_db.list_by_world(world_id_int)
            lore_parts: list[str] = []
            if world.lore:
                lore_parts.append(world.lore)
            for fact in all_facts:
                if not fact.is_injected and fact.content:
                    lore_parts.append(fact.content)
            world_lore = "\n\n".join(lore_parts)

        if req.field_type:
            system_prompt = build_world_field_editor_system(
                field_type=req.field_type,
                world_name=world.name,
                world_description=world.description,
                world_lore=world_lore,
                injected_lore=injected_lore,
                current_content=req.current_content,
                enable_tools=req.enable_tools,
            )
        else:
            system_prompt = build_document_editor_system(
                doc_type=req.doc_type,
                world_name=world.name,
                world_description=world.description,
                world_lore=world_lore,
                injected_lore=injected_lore,
                current_content=req.current_content,
                enable_tools=req.enable_tools,
            )

    client = await get_llm_client_for_model(req.model_id)

    messages: list[LLMMessage] = [
        {"role": m.role, "content": m.content} for m in req.messages
    ]

    options: dict = {
        "temperature": req.temperature,
        "top_p": req.top_p,
        "enable_thinking": req.enable_thinking,
    }

    async def generate():  # noqa: C901
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        in_thinking = False
        content_parts: list[str] = []

        async def on_delta(delta: str) -> None:
            nonlocal in_thinking
            text = delta

            # Entering thinking mode
            if not in_thinking and "<think>" in text:
                idx = text.index("<think>")
                before = text[:idx]
                after = text[idx + 7:]
                if before:
                    content_parts.append(before)
                    await queue.put(_sse_event("token", {"content": before}))
                in_thinking = True
                if after:
                    await queue.put(_sse_event("thinking", {"content": after}))
                return

            # Exiting thinking mode
            if in_thinking and "</think>" in text:
                idx = text.index("</think>")
                before = text[:idx]
                after = text[idx + 8:]
                if before:
                    await queue.put(_sse_event("thinking", {"content": before}))
                await queue.put(_sse_event("thinking_done", {}))
                in_thinking = False
                if after:
                    content_parts.append(after)
                    await queue.put(_sse_event("token", {"content": after}))
                return

            # Normal flow
            if in_thinking:
                await queue.put(_sse_event("thinking", {"content": text}))
            else:
                content_parts.append(text)
                await queue.put(_sse_event("token", {"content": text}))

        async def run_llm() -> None:
            try:
                if req.enable_tools:
                    await _run_with_tools(
                        client,
                        messages,
                        system_prompt,
                        options,
                        queue,
                        content_parts,
                        world_id_int,
                        world_agnostic=is_pipeline_prompt,
                    )
                else:
                    async with client:
                        await client.chat(
                            messages,
                            system=system_prompt,
                            options=options,
                            stream=True,
                            on_delta=on_delta,
                        )
                    full_content = "".join(content_parts)
                    await queue.put(_sse_event("done", {"content": full_content}))
            except Exception as exc:
                logger.exception("LLM chat stream error")
                await queue.put(_sse_event("error", {"message": str(exc)}))
            finally:
                await queue.put(None)  # sentinel

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

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/translate")
async def translate_text(
    req: TranslateRequest,
    _caller: User = Depends(_require_editor),
) -> StreamingResponse:
    return StreamingResponse(
        llm_chat_service.translate_to_english_stream(
            req.text,
            req.model_id,
            temperature=req.temperature,
            top_p=req.top_p,
            repeat_penalty=req.repeat_penalty,
            enable_thinking=req.enable_thinking,
        ),
        media_type="text/event-stream",
    )
