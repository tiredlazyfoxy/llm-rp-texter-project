"""Tuning profile service — business logic for the per-(user, world) profile API."""

from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.db import chats as chats_db
from app.db import tuning_profiles as tuning_profiles_db
from app.models.chat_tuning_profile import ChatTuningProfile
from app.models.schemas.chat import (
    RetuneStatusResponse,
    TuningProfileResponse,
    UpdateTuningProfileRequest,
)
from app.services import retune_tasks
from app.services import snowflake as snowflake_svc


def _to_response(profile: ChatTuningProfile) -> TuningProfileResponse:
    return TuningProfileResponse(
        id=str(profile.id),
        world_id=str(profile.world_id),
        plan_tuning=profile.plan_tuning,
        tone_tuning=profile.tone_tuning,
    )


async def get_profile(user_id: int, world_id: int) -> TuningProfileResponse:
    row = await tuning_profiles_db.get(user_id, world_id)
    if row is None:
        return TuningProfileResponse(
            id="", world_id=str(world_id), plan_tuning="", tone_tuning="",
        )
    return _to_response(row)


async def update_profile(
    user_id: int, world_id: int, req: UpdateTuningProfileRequest,
) -> TuningProfileResponse:
    now = datetime.now(timezone.utc)
    profile = await tuning_profiles_db.get(user_id, world_id)
    if profile is None:
        profile = ChatTuningProfile(
            id=snowflake_svc.generate_id(),
            user_id=user_id,
            world_id=world_id,
            plan_tuning=req.plan_tuning,
            tone_tuning=req.tone_tuning,
            created_at=now,
            modified_at=now,
        )
    else:
        profile.plan_tuning = req.plan_tuning
        profile.tone_tuning = req.tone_tuning
        profile.modified_at = now
    saved = await tuning_profiles_db.upsert(profile)
    return _to_response(saved)


# ---------------------------------------------------------------------------
# Background retune — session-scoped trigger / stop / status (Feature 015)
# ---------------------------------------------------------------------------


async def _load_owned_chat(chat_id: int, user_id: int):
    """Load the chat and enforce ownership (404-only, no 403)."""
    chat = await chats_db.get_session_by_id(chat_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found",
        )
    return chat


async def _build_status(chat) -> RetuneStatusResponse:
    """Build the combined status view (running flag + current profile values)."""
    snapshot = retune_tasks.status(chat.id)
    profile = await tuning_profiles_db.get(user_id=chat.user_id, world_id=chat.world_id)
    if profile is None:
        plan_tuning = ""
        tone_tuning = ""
    else:
        plan_tuning = profile.plan_tuning
        tone_tuning = profile.tone_tuning
    return RetuneStatusResponse(
        running=snapshot["running"],
        plan_tuning=plan_tuning,
        tone_tuning=tone_tuning,
        world_id=str(chat.world_id),
    )


async def trigger_retune(chat_id: int, user_id: int) -> RetuneStatusResponse:
    """Manually start a background retune for the chat's session.

    Loads the chat, verifies ownership (404 on mismatch), then fires the
    registry with ``turn_number=None`` (manual trigger ignores the D2 gate).
    Returns the current status shape.
    """
    chat = await _load_owned_chat(chat_id, user_id)
    await retune_tasks.start(
        session_id=chat.id,
        user_id=user_id,
        world_id=chat.world_id,
        model_id=chat.text_model_id,
        turn_number=None,
    )
    return await _build_status(chat)


async def stop_retune(chat_id: int, user_id: int) -> RetuneStatusResponse:
    """Cancel the running background retune for the chat's session (no restart).

    Loads the chat, verifies ownership (404 on mismatch), calls
    ``retune_tasks.stop``, and returns the current status shape.
    """
    chat = await _load_owned_chat(chat_id, user_id)
    await retune_tasks.stop(chat.id)
    return await _build_status(chat)


async def get_retune_status(chat_id: int, user_id: int) -> RetuneStatusResponse:
    """Return the running flag plus the current (user, world) profile values.

    Loads the chat, verifies ownership (404 on mismatch), reads the sync
    ``retune_tasks.status`` for the running flag and loads the profile so a
    single poll learns both the running->idle edge and the new values.
    """
    chat = await _load_owned_chat(chat_id, user_id)
    return await _build_status(chat)
