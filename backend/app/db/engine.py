import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models.pipeline  # noqa: F401
import app.models.world  # noqa: F401 — register world tables with SQLModel metadata
import app.models.chat_session  # noqa: F401
import app.models.chat_summary  # noqa: F401
import app.models.chat_message  # noqa: F401
import app.models.chat_state_snapshot  # noqa: F401
import app.models.chat_memory  # noqa: F401
import app.models.user_settings  # noqa: F401

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "llmrp.db"


@dataclass
class DbConfig:
    """Injectable DB configuration. Override for tests or different environments."""

    db_path: Path = field(default_factory=lambda: _DEFAULT_DB_PATH)
    echo: bool = False


_config: DbConfig = DbConfig()
_engine = None
_db_ready = False


def _get_db_url() -> str:
    return f"sqlite+aiosqlite:///{_config.db_path}"


async def init_engine(config: DbConfig | None = None) -> None:
    """Initialize the async engine. Accepts optional config for tests."""
    global _engine, _db_ready, _config
    if config is not None:
        _config = config
    _config.db_path.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_async_engine(_get_db_url(), echo=_config.echo)
    _db_ready = has_database()
    if _db_ready:
        logger.info("Database found at %s", _config.db_path)
    else:
        logger.info("No database found — setup required")


def has_database() -> bool:
    """Check if DB file exists and has content."""
    return _config.db_path.exists() and _config.db_path.stat().st_size > 0


def is_db_ready() -> bool:
    return _db_ready


def set_db_ready(value: bool) -> None:
    global _db_ready
    _db_ready = value


async def init_db() -> None:
    """Create all SQLModel tables (idempotent). Call before import or on first start."""
    global _engine
    if _engine is None:
        _config.db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_async_engine(_get_db_url(), echo=_config.echo)

    async with _engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Lightweight migrations for columns added after initial schema
    from sqlalchemy import text
    async with _engine.begin() as conn:
        try:
            await conn.execute(text(
                "ALTER TABLE chat_messages ADD COLUMN user_instructions TEXT"
            ))
            logger.info("Migration: added user_instructions column to chat_messages")
        except Exception:
            pass  # column already exists
        try:
            await conn.execute(text("ALTER TABLE worlds ADD COLUMN pipeline_id BIGINT"))
            logger.info("Migration: added pipeline_id column to worlds")
        except Exception:
            pass  # column already exists


async def get_standalone_session() -> AsyncSession:
    """Create a standalone session (internal to db layer only)."""
    if _engine is None:
        raise RuntimeError("Database engine not initialized")
    return AsyncSession(_engine)
