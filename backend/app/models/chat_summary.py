from datetime import datetime

from sqlmodel import Field, SQLModel


class ChatSummary(SQLModel, table=True):
    __tablename__ = "chat_summaries"

    id: int = Field(primary_key=True)
    session_id: int = Field(foreign_key="chat_sessions.id", index=True)
    start_message_id: int = Field(foreign_key="chat_messages.id")
    end_message_id: int = Field(foreign_key="chat_messages.id")
    start_turn: int
    end_turn: int
    content: str
    created_at: datetime
