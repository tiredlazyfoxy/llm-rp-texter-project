import asyncio
import logging
import random
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.db.engine import is_db_ready
from app.db.user_queries import get_user_by_username, update_user
from app.models.schemas.auth import (
    AuthStatusResponse,
    CreateDBRequest,
    LoginRequest,
    LoginResponse,
)
from app.services.auth import (
    create_token,
    maybe_rotate_signing_key,
    verify_password,
)
from app.services.database import create_database, import_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Rate limiting: {username: (fail_count, cooldown_until_timestamp)}
_login_attempts: dict[str, tuple[int, float]] = {}
_MAX_ATTEMPTS = 4
_COOLDOWN_SECONDS = 60


async def _random_delay() -> None:
    await asyncio.sleep(random.uniform(0.1, 0.3))


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status() -> AuthStatusResponse:
    return AuthStatusResponse(needs_setup=not is_db_ready())


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    await _random_delay()

    if not is_db_ready():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Database not set up")

    # Check rate limit
    attempt_info = _login_attempts.get(body.username)
    if attempt_info:
        fail_count, cooldown_until = attempt_info
        if fail_count >= _MAX_ATTEMPTS and time.time() < cooldown_until:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Wrong credentials",
            )
        if time.time() >= cooldown_until:
            _login_attempts.pop(body.username, None)

    user = await get_user_by_username(body.username)

    if user is None or user.pwdhash is None or user.salt is None:
        _record_failure(body.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong credentials")

    if not verify_password(body.password, user.salt, user.pwdhash):
        _record_failure(body.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong credentials")

    # Success — clear attempts, rotate key if needed, update last_login
    _login_attempts.pop(body.username, None)
    maybe_rotate_signing_key(user)
    user.last_login = datetime.now(timezone.utc)

    await update_user(user)

    token = create_token(user)
    return LoginResponse(token=token)


@router.post("/setup/create", response_model=LoginResponse)
async def setup_create(body: CreateDBRequest) -> LoginResponse:
    await _random_delay()

    if is_db_ready():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Database already exists")

    if body.password != body.password_confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

    if len(body.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password too short (min 6)")

    admin = await create_database(body.admin_username, body.password)
    token = create_token(admin)
    return LoginResponse(token=token)


@router.post("/setup/import")
async def setup_import(file: UploadFile) -> AuthStatusResponse:
    await _random_delay()

    if is_db_ready():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Database already exists")

    zip_data = await file.read()
    await import_database(zip_data)
    return AuthStatusResponse(needs_setup=False)


def _record_failure(username: str) -> None:
    attempt_info = _login_attempts.get(username)
    if attempt_info:
        fail_count, _ = attempt_info
        fail_count += 1
    else:
        fail_count = 1

    cooldown_until = time.time() + _COOLDOWN_SECONDS if fail_count >= _MAX_ATTEMPTS else 0
    _login_attempts[username] = (fail_count, cooldown_until)
