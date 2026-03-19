from datetime import datetime

from pydantic import BaseModel

from app.models.user import UserRole


class AdminUserResponse(BaseModel):
    id: str
    username: str
    role: UserRole
    last_login: datetime | None


class AdminCreateUserRequest(BaseModel):
    username: str
    password: str
    password_confirm: str
    role: UserRole


class AdminSetPasswordRequest(BaseModel):
    password: str
    password_confirm: str


class AdminSetRoleRequest(BaseModel):
    role: UserRole
