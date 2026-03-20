"""Chat API routes — session management and SSE streaming."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.responses import StreamingResponse

from app.models.schemas.llm_servers import EnabledModelsListResponse
from app.services import llm_servers as llm_service
from app.models.schemas.chat import (
    ChatDetailResponse,
    ChatSessionListResponse,
    ChatSessionResponse,
    ChatSummaryResponse,
    ContinueRequest,
    CreateChatRequest,
    RewindRequest,
    SendMessageRequest,
    UpdateChatSettingsRequest,
    WorldInfoResponse,
)
from app.models.user import User, UserRole
from app.services import chat_service
from app.services import chat_agent_service
from app.services.auth import require_role

logger = logging.getLogger(__name__)

_require_player = require_role(UserRole.player)

router = APIRouter(prefix="/api/chats", tags=["chats"])


# ---------------------------------------------------------------------------
# Models (player-facing — separate from admin /api/llm/models)
# ---------------------------------------------------------------------------

@router.get("/models", response_model=EnabledModelsListResponse)
async def list_chat_models(
    _caller: User = Depends(_require_player),
) -> EnabledModelsListResponse:
    models = await llm_service.get_all_enabled_models()
    return EnabledModelsListResponse(models=models)


# ---------------------------------------------------------------------------
# Worlds
# ---------------------------------------------------------------------------

@router.get("/worlds", response_model=list[WorldInfoResponse])
async def list_public_worlds(
    caller: User = Depends(_require_player),
) -> list[WorldInfoResponse]:
    return await chat_service.list_public_worlds(caller_id=caller.id)


# ---------------------------------------------------------------------------
# Chat sessions
# ---------------------------------------------------------------------------

@router.post("", response_model=ChatSessionResponse)
async def create_chat(
    req: CreateChatRequest,
    caller: User = Depends(_require_player),
) -> ChatSessionResponse:
    return await chat_service.create_chat(
        world_id=int(req.world_id),
        user_id=caller.id,
        character_name=req.character_name,
        template_variables=req.template_variables,
        starting_location_id=int(req.starting_location_id),
        tool_model=req.tool_model,
        text_model=req.text_model,
    )


@router.get("", response_model=ChatSessionListResponse)
async def list_chats(
    caller: User = Depends(_require_player),
) -> ChatSessionListResponse:
    items = await chat_service.list_user_sessions(caller.id)
    return ChatSessionListResponse(items=items)


@router.get("/{chat_id}", response_model=ChatDetailResponse)
async def get_chat(
    chat_id: str,
    caller: User = Depends(_require_player),
) -> ChatDetailResponse:
    return await chat_service.get_chat_detail(int(chat_id), caller.id)


# ---------------------------------------------------------------------------
# Messaging / generation
# ---------------------------------------------------------------------------

@router.post("/{chat_id}/message")
async def send_message(
    chat_id: str,
    req: SendMessageRequest,
    caller: User = Depends(_require_player),
) -> StreamingResponse:
    generator = await chat_agent_service.generate_response(int(chat_id), caller.id, req.content)
    return StreamingResponse(generator, media_type="text/event-stream")


@router.post("/{chat_id}/regenerate")
async def regenerate(
    chat_id: str,
    caller: User = Depends(_require_player),
) -> StreamingResponse:
    generator = await chat_agent_service.regenerate_response(int(chat_id), caller.id)
    return StreamingResponse(generator, media_type="text/event-stream")


@router.post("/{chat_id}/continue", response_model=dict)
async def continue_chat(
    chat_id: str,
    req: ContinueRequest,
    caller: User = Depends(_require_player),
) -> dict:
    await chat_service.continue_chat(int(chat_id), caller.id, int(req.selected_variant_id))
    return {"ok": True}


@router.post("/{chat_id}/rewind", response_model=ChatDetailResponse)
async def rewind_chat(
    chat_id: str,
    req: RewindRequest,
    caller: User = Depends(_require_player),
) -> ChatDetailResponse:
    return await chat_service.rewind_chat(int(chat_id), caller.id, req.target_turn)


# ---------------------------------------------------------------------------
# Settings / lifecycle
# ---------------------------------------------------------------------------

@router.put("/{chat_id}/settings", response_model=dict)
async def update_settings(
    chat_id: str,
    req: UpdateChatSettingsRequest,
    caller: User = Depends(_require_player),
) -> dict:
    await chat_service.update_settings(
        int(chat_id), caller.id, req.tool_model, req.text_model, req.user_instructions
    )
    return {"ok": True}


@router.put("/{chat_id}/archive", response_model=dict)
async def archive_chat(
    chat_id: str,
    caller: User = Depends(_require_player),
) -> dict:
    await chat_service.archive_chat(int(chat_id), caller.id)
    return {"ok": True}


@router.delete("/{chat_id}", response_model=dict)
async def delete_chat(
    chat_id: str,
    caller: User = Depends(_require_player),
) -> dict:
    await chat_service.delete_chat(int(chat_id), caller.id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Memories
# ---------------------------------------------------------------------------

@router.get("/{chat_id}/memories", response_model=list[ChatSummaryResponse])
async def list_memories(
    chat_id: str,
    caller: User = Depends(_require_player),
) -> list[ChatSummaryResponse]:
    return await chat_service.list_memories(int(chat_id), caller.id)


@router.delete("/{chat_id}/memories/{memory_id}", response_model=dict)
async def delete_memory(
    chat_id: str,
    memory_id: str,
    caller: User = Depends(_require_player),
) -> dict:
    await chat_service.delete_memory(int(chat_id), int(memory_id), caller.id)
    return {"ok": True}
