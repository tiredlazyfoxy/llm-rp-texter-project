"""User settings service — business logic for per-user preferences."""

from app.db import user_settings as db
from app.models.schemas.user_settings import (
    TranslationSettingsResponse,
    UpdateTranslationSettingsRequest,
)
from app.models.user_settings import UserSettings


def _to_response(s: UserSettings) -> TranslationSettingsResponse:
    return TranslationSettingsResponse(
        translate_model_id=s.translate_model_id,
        translate_temperature=s.translate_temperature,
        translate_top_p=s.translate_top_p,
        translate_repeat_penalty=s.translate_repeat_penalty,
        translate_think=s.translate_think,
    )


_DEFAULTS = TranslationSettingsResponse(
    translate_model_id=None,
    translate_temperature=0.1,
    translate_top_p=1.0,
    translate_repeat_penalty=1.0,
    translate_think=False,
)


async def get_translation_settings(user_id: int) -> TranslationSettingsResponse:
    row = await db.get(user_id)
    if row is None:
        return _DEFAULTS
    return _to_response(row)


async def update_translation_settings(
    user_id: int, req: UpdateTranslationSettingsRequest,
) -> TranslationSettingsResponse:
    settings = UserSettings(
        user_id=user_id,
        translate_model_id=req.translate_model_id,
        translate_temperature=req.translate_temperature,
        translate_top_p=req.translate_top_p,
        translate_repeat_penalty=req.translate_repeat_penalty,
        translate_think=req.translate_think,
    )
    saved = await db.upsert(settings)
    return _to_response(saved)
