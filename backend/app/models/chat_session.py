from datetime import datetime

from sqlmodel import Field, SQLModel


class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_sessions"

    id: int = Field(primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    world_id: int = Field(foreign_key="worlds.id", index=True)
    current_location_id: int | None = Field(default=None, foreign_key="world_locations.id")
    character_name: str
    character_description: str
    character_stats: str = Field(default="{}")
    world_stats: str = Field(default="{}")
    current_turn: int = Field(default=0)
    status: str = Field(default="active")
    tool_model_id: str | None = None
    tool_temperature: float = Field(default=0.7)
    tool_repeat_penalty: float = Field(default=1.0)
    tool_top_p: float = Field(default=1.0)
    text_model_id: str | None = None
    text_temperature: float = Field(default=0.7)
    text_repeat_penalty: float = Field(default=1.0)
    text_top_p: float = Field(default=1.0)
    user_instructions: str = Field(default="")
    created_at: datetime
    modified_at: datetime
