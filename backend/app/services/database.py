import logging
from datetime import datetime, timezone

from app.db import engine as db_engine
from app.models.user import User, UserRole
from app.services import snowflake

logger = logging.getLogger(__name__)


async def create_database(admin_username: str, password: str) -> User:
    """Create DB tables and initial admin user. Returns the admin User."""
    await db_engine.init_db()

    from app.db import users
    from app.services import auth as auth_service

    salt, pwdhash, signing_key = auth_service.create_user_credentials(password)
    now = datetime.now(timezone.utc)

    admin = User(
        id=snowflake.generate_id(),
        username=admin_username,
        pwdhash=pwdhash,
        salt=salt,
        role=UserRole.admin,
        jwt_signing_key=signing_key,
        last_login=now,
        last_key_update=now,
    )
    admin = await users.create(admin)

    db_engine.set_db_ready(True)
    logger.info("Database created with admin user '%s'", admin_username)
    return admin


async def import_database(zip_data: bytes) -> None:
    """Import data from zip. Tables are created by import_all via init_db()."""
    from app.db import import_export_queries
    from app.services import db_import_export

    await db_import_export.import_all(zip_data)
    await import_export_queries.run_vector_rebuild()

    db_engine.set_db_ready(True)
    logger.info("Database imported from zip")
