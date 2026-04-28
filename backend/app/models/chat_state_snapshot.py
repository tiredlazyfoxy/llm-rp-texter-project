from datetime import datetime

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


class ChatStateSnapshot(SQLModel, table=True):
    __tablename__ = "chat_state_snapshots"
    __table_args__ = (Index("ix_chat_state_snapshots_session_turn", "session_id", "turn_number"),)

    id: int = Field(primary_key=True)
    session_id: int = Field(foreign_key="chat_sessions.id", index=True)
    turn_number: int
    location_id: int | None = None
    character_stats: str = Field(default="{}")
    world_stats: str = Field(default="{}")
    created_at: datetime
