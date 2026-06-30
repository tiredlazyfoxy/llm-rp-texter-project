"""Tuning profile service — business logic for the per-(user, world) profile API."""

from datetime import datetime, timezone

from app.db import tuning_profiles as tuning_profiles_db
from app.models.chat_tuning_profile import ChatTuningProfile
from app.models.schemas.chat import TuningProfileResponse, UpdateTuningProfileRequest
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
