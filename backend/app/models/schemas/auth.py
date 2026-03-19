from pydantic import BaseModel

from app.models.user import UserRole


class UserResponse(BaseModel):
    id: str
    username: str
    role: UserRole


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str


class CreateDBRequest(BaseModel):
    admin_username: str
    password: str
    password_confirm: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    new_password_confirm: str


class AuthStatusResponse(BaseModel):
    needs_setup: bool
