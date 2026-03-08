"""Admin business logic — user management."""

from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.db import users
from app.models.user import User, UserRole
from app.services import auth as auth_service
from app.services.snowflake import generate_id


async def list_users() -> list[User]:
    return await users.get_all()


async def create_user(username: str, password: str, role: UserRole) -> User:
    existing = await users.get_by_username(username)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    salt, pwdhash, signing_key = auth_service.create_user_credentials(password)
    user = User(
        id=generate_id(),
        username=username,
        salt=salt,
        pwdhash=pwdhash,
        jwt_signing_key=signing_key,
        role=role,
        last_key_update=datetime.now(timezone.utc),
    )
    return await users.create(user)


async def set_user_password(user_id: int, password: str) -> None:
    user = await _get_user_or_404(user_id)

    salt, pwdhash, signing_key = auth_service.create_user_credentials(password)
    user.salt = salt
    user.pwdhash = pwdhash
    user.jwt_signing_key = signing_key
    user.last_key_update = datetime.now(timezone.utc)

    await users.update(user)


async def set_user_role(user_id: int, role: UserRole, caller: User) -> None:
    if caller.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )

    user = await _get_user_or_404(user_id)
    user.role = role
    await users.update(user)


async def disable_user(user_id: int, caller: User) -> None:
    if caller.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot disable yourself",
        )

    user = await _get_user_or_404(user_id)

    if user.pwdhash is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already disabled",
        )

    user.pwdhash = None
    user.salt = None
    user.jwt_signing_key = None
    await users.update(user)


async def _get_user_or_404(user_id: int) -> User:
    user = await users.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user
