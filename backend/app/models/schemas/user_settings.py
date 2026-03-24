"""Pydantic schemas for user settings endpoints."""

from pydantic import BaseModel


class TranslationSettingsResponse(BaseModel):
    translate_model_id: str | None
    translate_temperature: float
    translate_top_p: float
    translate_repeat_penalty: float
    translate_think: bool


class UpdateTranslationSettingsRequest(BaseModel):
    translate_model_id: str | None = None
    translate_temperature: float = 0.1
    translate_top_p: float = 1.0
    translate_repeat_penalty: float = 1.0
    translate_think: bool = False
