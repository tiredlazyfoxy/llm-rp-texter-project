import logging
from datetime import datetime, timezone

from app.db.engine import init_db, set_db_ready
from app.models.user import User, UserRole
from app.services.snowflake import generate_id

logger = logging.getLogger(__name__)


async def create_database(admin_username: str, password: str) -> User:
    """Create DB tables and initial admin user. Returns the admin User."""
    await init_db()

    from app.db.user_queries import create_user
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
    admin = await create_user(admin)

    set_db_ready(True)
    logger.info("Database created with admin user '%s'", admin_username)
    return admin


async def import_database(zip_data: bytes) -> None:
    """Import data from zip. Tables are created by import_all via init_db()."""
    from app.db.import_export_queries import run_vector_rebuild
    from app.services.db_import_export import import_all

    await import_all(zip_data)
    await run_vector_rebuild()

    set_db_ready(True)
    logger.info("Database imported from zip")
