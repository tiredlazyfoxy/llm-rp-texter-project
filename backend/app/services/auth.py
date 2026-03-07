import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import bcrypt as _bcrypt

from app.models.user import User, UserRole
from app.services.database import get_session

_bearer_scheme = HTTPBearer()


def _generate_salt() -> str:
    return secrets.token_hex(16)


def _generate_signing_key() -> str:
    return secrets.token_hex(32)


def hash_password(password: str, salt: str) -> str:
    salted = (salt + password).encode("utf-8")
    return _bcrypt.hashpw(salted, _bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, salt: str, pwdhash: str) -> bool:
    salted = (salt + password).encode("utf-8")
    return _bcrypt.checkpw(salted, pwdhash.encode("utf-8"))


def create_token(user: User) -> str:
    if user.jwt_signing_key is None:
        raise ValueError("User has no signing key")
    payload = {
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role.value,
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
    }
    return jwt.encode(payload, user.jwt_signing_key, algorithm="HS256")


def create_user_credentials(password: str) -> tuple[str, str, str]:
    """Returns (salt, pwdhash, jwt_signing_key) for a new user or password change."""
    salt = _generate_salt()
    pwdhash = hash_password(password, salt)
    signing_key = _generate_signing_key()
    return salt, pwdhash, signing_key


async def verify_token(token: str) -> dict:
    """Decode token without verification to get user_id, then verify with user's key."""
    from sqlmodel import select

    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
    except jwt.DecodeError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = int(unverified.get("user_id", 0))
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    async for session in get_session():
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

    if user is None or user.jwt_signing_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        payload = jwt.decode(token, user.jwt_signing_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return payload


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> User:
    """FastAPI dependency: extracts and validates JWT, returns User."""
    from sqlmodel import select

    payload = await verify_token(credentials.credentials)
    user_id = int(payload["user_id"])

    async for session in get_session():
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

    if user is None or user.pwdhash is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User disabled")

    return user


def maybe_rotate_signing_key(user: User) -> bool:
    """Rotate JWT signing key if last_key_update is older than 30 days. Returns True if rotated."""
    now = datetime.now(timezone.utc)
    last_update = user.last_key_update
    if last_update is not None and last_update.tzinfo is None:
        last_update = last_update.replace(tzinfo=timezone.utc)
    if last_update is None or (now - last_update) > timedelta(days=30):
        user.jwt_signing_key = _generate_signing_key()
        user.last_key_update = now
        return True
    return False


def require_role(minimum_role: UserRole):
    """Factory for FastAPI dependency that checks minimum role level."""
    role_levels = {UserRole.player: 0, UserRole.editor: 1, UserRole.admin: 2}

    async def check_role(user: User = Depends(get_current_user)) -> User:
        if role_levels.get(user.role, 0) < role_levels[minimum_role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return check_role
