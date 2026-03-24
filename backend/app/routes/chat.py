"""Chat API routes — session management and SSE streaming."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.responses import StreamingResponse

from app.models.schemas.llm_servers import EnabledModelsListResponse
from app.services import llm_servers as llm_service
from app.models.schemas.chat import (
    ChatDetailResponse,
    ChatMessageResponse,
    ChatSessionListResponse,
    ChatSessionResponse,
    ChatSummaryResponse,
    CompactRequest,
    CompactResponse,
    ContinueRequest,
    CreateChatRequest,
    EditMessageRequest,
    RegenerateRequest,
    RewindRequest,
    SendMessageRequest,
    UpdateChatSettingsRequest,
    WorldInfoResponse,
)
from app.models.schemas.llm_chat import TranslateRequest
from app.models.user import User, UserRole
from app.services import chat_service
from app.services import chat_agent_service
from app.services import llm_chat as llm_chat_service
from app.services import summarization_service
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


@router.post("/translate")
async def translate_chat_text(
    req: TranslateRequest,
    _caller: User = Depends(_require_player),
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
    return await chat_service.get_chat_detail(int(chat_id), caller.id, caller.role.value)


# ---------------------------------------------------------------------------
# Messaging / generation
# ---------------------------------------------------------------------------

@router.post("/{chat_id}/message")
async def send_message(
    chat_id: str,
    req: SendMessageRequest,
    caller: User = Depends(_require_player),
) -> StreamingResponse:
    generator = await chat_agent_service.generate_response(
        int(chat_id), caller.id, req.content, caller_role=caller.role.value,
        variant_index=req.variant_index,
    )
    return StreamingResponse(generator, media_type="text/event-stream")


@router.post("/{chat_id}/regenerate")
async def regenerate(
    chat_id: str,
    req: RegenerateRequest | None = None,
    caller: User = Depends(_require_player),
) -> StreamingResponse:
    turn = req.turn_number if req else None
    generator = await chat_agent_service.regenerate_response(
        int(chat_id), caller.id, caller_role=caller.role.value,
        turn_number=turn,
    )
    return StreamingResponse(generator, media_type="text/event-stream")


@router.put("/{chat_id}/messages/{message_id}", response_model=ChatDetailResponse)
async def edit_message(
    chat_id: str,
    message_id: str,
    req: EditMessageRequest,
    caller: User = Depends(_require_player),
) -> ChatDetailResponse:
    return await chat_service.edit_message(
        int(chat_id), int(message_id), req.content, caller.id, caller.role.value,
    )


@router.delete("/{chat_id}/messages/{message_id}", response_model=ChatDetailResponse)
async def delete_message(
    chat_id: str,
    message_id: str,
    caller: User = Depends(_require_player),
) -> ChatDetailResponse:
    return await chat_service.delete_message(
        int(chat_id), int(message_id), caller.id, caller.role.value,
    )


@router.post("/{chat_id}/continue", response_model=dict)
async def continue_chat(
    chat_id: str,
    req: ContinueRequest,
    caller: User = Depends(_require_player),
) -> dict:
    await chat_service.continue_chat(int(chat_id), caller.id, req.variant_index)
    return {"ok": True}


@router.post("/{chat_id}/rewind", response_model=ChatDetailResponse)
async def rewind_chat(
    chat_id: str,
    req: RewindRequest,
    caller: User = Depends(_require_player),
) -> ChatDetailResponse:
    return await chat_service.rewind_chat(int(chat_id), caller.id, req.target_turn, caller.role.value)


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


# ---------------------------------------------------------------------------
# Summaries / compaction
# ---------------------------------------------------------------------------

@router.post("/{chat_id}/compact", response_model=CompactResponse)
async def compact_chat(
    chat_id: str,
    req: CompactRequest,
    caller: User = Depends(_require_player),
) -> CompactResponse:
    summary, count = await summarization_service.compact_messages(
        int(chat_id), int(req.up_to_message_id), caller.id,
    )
    return CompactResponse(
        summary=ChatSummaryResponse(
            id=str(summary.id),
            start_message_id=str(summary.start_message_id),
            end_message_id=str(summary.end_message_id),
            start_turn=summary.start_turn,
            end_turn=summary.end_turn,
            content=summary.content,
            created_at=summary.created_at.isoformat(),
        ),
        updated_message_count=count,
    )


@router.post("/{chat_id}/summaries/{summary_id}/regenerate", response_model=ChatSummaryResponse)
async def regenerate_summary(
    chat_id: str,
    summary_id: str,
    caller: User = Depends(_require_player),
) -> ChatSummaryResponse:
    summary = await summarization_service.regenerate_summary(int(summary_id), caller.id)
    return ChatSummaryResponse(
        id=str(summary.id),
        start_message_id=str(summary.start_message_id),
        end_message_id=str(summary.end_message_id),
        start_turn=summary.start_turn,
        end_turn=summary.end_turn,
        content=summary.content,
        created_at=summary.created_at.isoformat(),
    )


@router.get("/{chat_id}/summaries", response_model=list[ChatSummaryResponse])
async def list_summaries(
    chat_id: str,
    caller: User = Depends(_require_player),
) -> list[ChatSummaryResponse]:
    return await chat_service.list_memories(int(chat_id), caller.id)


@router.get(
    "/{chat_id}/summaries/{summary_id}/messages",
    response_model=list[ChatMessageResponse],
)
async def get_summary_messages(
    chat_id: str,
    summary_id: str,
    caller: User = Depends(_require_player),
) -> list[ChatMessageResponse]:
    return await chat_service.get_summary_messages(int(chat_id), int(summary_id), caller.id)
