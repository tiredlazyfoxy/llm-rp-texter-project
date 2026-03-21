from datetime import datetime

from sqlmodel import Field, SQLModel


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: int = Field(primary_key=True)
    session_id: int = Field(foreign_key="chat_sessions.id", index=True)
    role: str
    content: str
    turn_number: int = Field(index=True)
    tool_calls: str | None = None
    generation_plan: str | None = Field(default=None)
    thinking_content: str | None = Field(default=None)
    summary_id: int | None = Field(default=None, foreign_key="chat_summaries.id", index=True)
    is_active_variant: bool = Field(default=True)
    created_at: datetime
