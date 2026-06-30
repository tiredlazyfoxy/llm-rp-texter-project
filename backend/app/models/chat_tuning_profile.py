from datetime import datetime

from sqlmodel import Field, SQLModel


class ChatTuningProfile(SQLModel, table=True):
    __tablename__ = "chat_tuning_profiles"

    id: int = Field(primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    world_id: int = Field(foreign_key="worlds.id", index=True)
    plan_tuning: str = Field(default="")
    tone_tuning: str = Field(default="")
    created_at: datetime
    modified_at: datetime
