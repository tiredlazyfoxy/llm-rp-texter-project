"""User settings — per-user global preferences (1:1 with users)."""

from sqlmodel import Field, SQLModel


class UserSettings(SQLModel, table=True):
    __tablename__ = "user_settings"

    user_id: int = Field(primary_key=True)
    translate_model_id: str | None = Field(default=None)
    translate_temperature: float = Field(default=0.1)
    translate_top_p: float = Field(default=1.0)
    translate_repeat_penalty: float = Field(default=1.0)
    translate_think: bool = Field(default=False)
