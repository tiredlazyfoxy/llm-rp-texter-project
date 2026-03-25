"""LLM prompt package — one documented file per prompt."""

from app.services.prompts.document_editor_system_prompt import build_document_editor_system
from app.services.prompts.world_field_editor_system_prompt import build_world_field_editor_system
from app.services.prompts.chat_summarization_prompt import (
    SUMMARIZE_SYSTEM_PROMPT,
    SUMMARIZE_USER_PROMPT_TEMPLATE,
)
from app.services.prompts.chat_system_prompt import build_rich_chat_system_prompt
from app.services.prompts.planning_system_prompt import build_planning_system_prompt
from app.services.prompts.writing_system_prompt import build_writing_system_prompt
from app.services.prompts.writing_plan_message import build_writing_plan_message
from app.services.prompts.placeholder_registry import PLACEHOLDER_REGISTRY, VALID_PLACEHOLDERS
from app.services.prompts.tool_catalog import TOOL_CATALOG, ALL_TOOL_NAMES
from app.services.prompts.default_templates import (
    DEFAULT_SIMPLE_PROMPT,
    DEFAULT_TOOL_PROMPT,
    DEFAULT_WRITER_PROMPT,
)

__all__ = [
    "build_rich_chat_system_prompt",
    "build_document_editor_system",
    "build_world_field_editor_system",
    "SUMMARIZE_SYSTEM_PROMPT",
    "SUMMARIZE_USER_PROMPT_TEMPLATE",
    "build_planning_system_prompt",
    "build_writing_system_prompt",
    "build_writing_plan_message",
    "PLACEHOLDER_REGISTRY",
    "VALID_PLACEHOLDERS",
    "TOOL_CATALOG",
    "ALL_TOOL_NAMES",
    "DEFAULT_SIMPLE_PROMPT",
    "DEFAULT_TOOL_PROMPT",
    "DEFAULT_WRITER_PROMPT",
]
