"""User settings routes — per-user global preferences."""

from fastapi import APIRouter, Depends

from app.models.schemas.user_settings import (
    TranslationSettingsResponse,
    UpdateTranslationSettingsRequest,
)
from app.models.user import User
from app.services import auth as auth_service
from app.services import user_settings as user_settings_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/translation", response_model=TranslationSettingsResponse)
async def get_translation_settings(
    user: User = Depends(auth_service.get_current_user),
) -> TranslationSettingsResponse:
    return await user_settings_service.get_translation_settings(user.id)


@router.put("/translation", response_model=TranslationSettingsResponse)
async def update_translation_settings(
    body: UpdateTranslationSettingsRequest,
    user: User = Depends(auth_service.get_current_user),
) -> TranslationSettingsResponse:
    return await user_settings_service.update_translation_settings(user.id, body)
