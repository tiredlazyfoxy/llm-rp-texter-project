from datetime import datetime

from sqlmodel import Field, SQLModel


class ChatMemory(SQLModel, table=True):
    __tablename__ = "chat_memories"

    id: int = Field(primary_key=True)
    session_id: int = Field(foreign_key="chat_sessions.id", index=True)
    content: str
    created_at: datetime
