import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import pytest

from app.db import users as users_db
from app.db.engine import DbConfig, init_db, init_engine
from app.models.user import User, UserRole
from app.services import auth as auth_service
from app.services import vector_storage
from app.services.snowflake import generate_id


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for all async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def test_db(tmp_path_factory: pytest.TempPathFactory):
    """Initialize DB engine, create tables, init vector store — for the entire test session."""
    tmp_dir: Path = tmp_path_factory.mktemp("test_data")

    # DB — temp SQLite file
    db_path = tmp_dir / "test.db"
    config = DbConfig(db_path=db_path, echo=False)
    await init_engine(config)
    await init_db()

    # Vector store — temp directory
    vector_dir = tmp_dir / "vector"
    await vector_storage.init_vector_store(vector_dir)

    yield db_path


async def _create_user(username: str, role: UserRole) -> tuple[User, str]:
    """Create a user with the given role and return (user, bearer_token)."""
    salt, pwdhash, signing_key = auth_service.create_user_credentials("password123")
    user = User(
        id=generate_id(),
        username=username,
        pwdhash=pwdhash,
        salt=salt,
        role=role,
        jwt_signing_key=signing_key,
        last_key_update=datetime.now(timezone.utc),
    )
    await users_db.create(user)
    token = auth_service.create_token(user)
    return user, token


@pytest.fixture
async def admin_user() -> AsyncIterator[tuple[User, str]]:
    user, token = await _create_user(f"admin_{generate_id()}", UserRole.admin)
    yield user, token


@pytest.fixture
async def editor_user() -> AsyncIterator[tuple[User, str]]:
    user, token = await _create_user(f"editor_{generate_id()}", UserRole.editor)
    yield user, token


@pytest.fixture
async def player_user() -> AsyncIterator[tuple[User, str]]:
    user, token = await _create_user(f"player_{generate_id()}", UserRole.player)
    yield user, token


@pytest.fixture
async def http_client() -> AsyncIterator:
    """httpx AsyncClient bound to the FastAPI app via ASGI transport."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
