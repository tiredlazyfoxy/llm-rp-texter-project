"""LLM prompt package — one documented file per prompt."""

from app.services.prompts.document_editor_system_prompt import build_document_editor_system
from app.services.prompts.world_field_editor_system_prompt import build_world_field_editor_system

__all__ = ["build_document_editor_system", "build_world_field_editor_system"]
