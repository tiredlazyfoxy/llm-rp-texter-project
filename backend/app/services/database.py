import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User, UserRole
import app.models.world  # noqa: F401 — register world tables with SQLModel metadata
from app.services.snowflake import generate_id

logger = logging.getLogger(__name__)

_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_DB_PATH = _DB_DIR / "llmrp.db"

_engine = None
_db_ready = False


def _get_db_url() -> str:
    return f"sqlite+aiosqlite:///{_DB_PATH}"


async def init_engine() -> None:
    """Initialize the async engine and check if DB exists."""
    global _engine, _db_ready
    _engine = create_async_engine(_get_db_url(), echo=False)
    _db_ready = has_database()
    if _db_ready:
        logger.info("Database found at %s", _DB_PATH)
    else:
        logger.info("No database found — setup required")


def has_database() -> bool:
    """Check if DB file exists and has content."""
    return _DB_PATH.exists() and _DB_PATH.stat().st_size > 0


def is_db_ready() -> bool:
    return _db_ready


async def create_all_tables() -> None:
    """Create all SQLModel tables."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(_get_db_url(), echo=False)

    async with _engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def create_database(admin_username: str, password: str) -> User:
    """Create DB tables and initial admin user. Returns the admin User."""
    global _db_ready

    _DB_DIR.mkdir(parents=True, exist_ok=True)
    await create_all_tables()

    from app.services.auth import create_user_credentials
    salt, pwdhash, signing_key = create_user_credentials(password)
    now = datetime.now(timezone.utc)

    admin = User(
        id=generate_id(),
        username=admin_username,
        pwdhash=pwdhash,
        salt=salt,
        role=UserRole.admin,
        jwt_signing_key=signing_key,
        last_login=now,
        last_key_update=now,
    )

    async with AsyncSession(_engine) as session:
        session.add(admin)
        await session.commit()
        await session.refresh(admin)

    _db_ready = True
    logger.info("Database created with admin user '%s'", admin_username)
    return admin


async def import_database(zip_data: bytes) -> None:
    """Create tables and import data from zip."""
    global _db_ready

    from app.services.db_import_export import import_all
    from app.services.vector_storage import rebuild_all_worlds_index

    _DB_DIR.mkdir(parents=True, exist_ok=True)
    await create_all_tables()

    async with AsyncSession(_engine) as session:
        await import_all(session, zip_data)
        await session.commit()

    # Rebuild vector indices from imported documents
    async with AsyncSession(_engine) as session:
        await rebuild_all_worlds_index(session)

    _db_ready = True
    logger.info("Database imported from zip")


async def get_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency: yields an async DB session."""
    if _engine is None:
        raise RuntimeError("Database engine not initialized")
    async with AsyncSession(_engine) as session:
        yield session
