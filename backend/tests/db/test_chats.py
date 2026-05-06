"""DB-layer tests for chat session persistence.

The chat-settings update flow at the service layer mutates the
SQLModel ``ChatSession`` row in-place and persists it via the
generic ``chats_db.update_session(chat)`` helper (no dedicated
settings-update helper exists in this codebase). These tests
verify that the generic helper persists the ``character_name``
field end-to-end, and that mutating one field while leaving
others untouched preserves the other fields.
"""

from datetime import datetime, timezone

from app.db import chats as chats_db
from app.models.chat_session import ChatSession
from app.services.snowflake import generate_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _create_chat(character_name: str = "Original") -> ChatSession:
    chat = ChatSession(
        id=generate_id(),
        user_id=generate_id(),
        world_id=generate_id(),
        current_location_id=None,
        character_name=character_name,
        character_description="",
        character_stats="{}",
        world_stats="{}",
        current_turn=0,
        status="active",
        tool_model_id=None,
        tool_temperature=0.7,
        tool_repeat_penalty=1.0,
        tool_top_p=1.0,
        text_model_id=None,
        text_temperature=0.7,
        text_repeat_penalty=1.0,
        text_top_p=1.0,
        user_instructions="",
        generation_variants="[]",
        created_at=_now(),
        modified_at=_now(),
    )
    return await chats_db.create_session(chat)


async def test_update_session_persists_character_name() -> None:
    chat = await _create_chat("Original")

    chat.character_name = "Bob"
    await chats_db.update_session(chat)

    refreshed = await chats_db.get_session_by_id(chat.id)
    assert refreshed is not None
    assert refreshed.character_name == "Bob"


async def test_update_session_tool_model_only_leaves_character_name_untouched() -> None:
    chat = await _create_chat("Original")

    chat.tool_model_id = "model-x"
    # character_name is intentionally NOT modified here.
    await chats_db.update_session(chat)

    refreshed = await chats_db.get_session_by_id(chat.id)
    assert refreshed is not None
    assert refreshed.tool_model_id == "model-x"
    assert refreshed.character_name == "Original"
