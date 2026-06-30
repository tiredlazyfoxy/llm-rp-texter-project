from datetime import datetime

from sqlmodel import Field, SQLModel


class ChatGenerationFeedback(SQLModel, table=True):
    __tablename__ = "chat_generation_feedback"

    id: int = Field(primary_key=True)
    session_id: int = Field(foreign_key="chat_sessions.id", index=True)
    turn_number: int = Field(index=True)
    verdict: str
    scope: str | None = Field(default=None)
    comment: str | None = Field(default=None)
    content_snapshot: str
    plan_snapshot: str | None = Field(default=None)
    created_at: datetime
