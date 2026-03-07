import enum
from datetime import datetime

from sqlmodel import Field, SQLModel


class UserRole(str, enum.Enum):
    admin = "admin"
    editor = "editor"
    player = "player"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int = Field(primary_key=True)
    username: str = Field(unique=True, index=True)
    pwdhash: str | None = Field(default=None)
    salt: str | None = Field(default=None)
    role: UserRole = Field(default=UserRole.player)
    jwt_signing_key: str | None = Field(default=None)
    last_login: datetime | None = Field(default=None)
    last_key_update: datetime | None = Field(default=None)
