import gzip
import io
import json
import zipfile
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User, UserRole


def _serialize_datetime(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _parse_datetime(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "pwdhash": user.pwdhash,
        "salt": user.salt,
        "role": user.role.value,
        "jwt_signing_key": user.jwt_signing_key,
        "last_login": _serialize_datetime(user.last_login),
        "last_key_update": _serialize_datetime(user.last_key_update),
    }


def _dict_to_user(d: dict) -> User:
    return User(
        id=d["id"],
        username=d["username"],
        pwdhash=d.get("pwdhash"),
        salt=d.get("salt"),
        role=UserRole(d["role"]),
        jwt_signing_key=d.get("jwt_signing_key"),
        last_login=_parse_datetime(d.get("last_login")),
        last_key_update=_parse_datetime(d.get("last_key_update")),
    )


async def export_users(session: AsyncSession) -> bytes:
    """Export users to gzipped JSONL."""
    result = await session.execute(select(User))
    users = result.scalars().all()

    lines = "\n".join(json.dumps(_user_to_dict(u)) for u in users)
    return gzip.compress(lines.encode("utf-8"))


async def import_users(session: AsyncSession, data: bytes) -> None:
    """Import users from gzipped JSONL."""
    raw = gzip.decompress(data).decode("utf-8")
    for line in raw.strip().split("\n"):
        if not line:
            continue
        user = _dict_to_user(json.loads(line))
        session.add(user)


async def export_all(session: AsyncSession) -> bytes:
    """Export all tables to a zip containing .jsonl.gz files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        users_data = await export_users(session)
        zf.writestr("users.jsonl.gz", users_data)
    return buf.getvalue()


async def import_all(session: AsyncSession, zip_data: bytes) -> None:
    """Import all tables from a zip of .jsonl.gz files."""
    buf = io.BytesIO(zip_data)
    with zipfile.ZipFile(buf, "r") as zf:
        if "users.jsonl.gz" in zf.namelist():
            await import_users(session, zf.read("users.jsonl.gz"))
