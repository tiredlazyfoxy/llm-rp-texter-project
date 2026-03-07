import gzip
import io
import json
import zipfile
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User, UserRole
from app.models.world import (
    NPCLinkType,
    NPCLocationLink,
    StatScope,
    StatType,
    World,
    WorldLocation,
    WorldLoreFact,
    WorldNPC,
    WorldRule,
    WorldStatDefinition,
    WorldStatus,
)


def _serialize_datetime(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _parse_datetime(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Worlds
# ---------------------------------------------------------------------------


def _world_to_dict(w: World) -> dict:
    return {
        "id": w.id,
        "name": w.name,
        "description": w.description,
        "lore": w.lore,
        "system_prompt": w.system_prompt,
        "character_template": w.character_template,
        "initial_message": w.initial_message,
        "pipeline": w.pipeline,
        "status": w.status.value,
        "created_at": _serialize_datetime(w.created_at),
        "modified_at": _serialize_datetime(w.modified_at),
    }


def _dict_to_world(d: dict) -> World:
    return World(
        id=d["id"],
        name=d["name"],
        description=d.get("description", ""),
        lore=d.get("lore", ""),
        system_prompt=d.get("system_prompt", ""),
        character_template=d.get("character_template", ""),
        initial_message=d.get("initial_message", ""),
        pipeline=d.get("pipeline", "{}"),
        status=WorldStatus(d["status"]),
        created_at=_parse_datetime(d.get("created_at")),
        modified_at=_parse_datetime(d.get("modified_at")),
    )


async def export_worlds(session: AsyncSession) -> bytes:
    result = await session.execute(select(World))
    items = result.scalars().all()
    lines = "\n".join(json.dumps(_world_to_dict(i)) for i in items)
    return gzip.compress(lines.encode("utf-8"))


async def import_worlds(session: AsyncSession, data: bytes) -> None:
    raw = gzip.decompress(data).decode("utf-8")
    for line in raw.strip().split("\n"):
        if not line:
            continue
        session.add(_dict_to_world(json.loads(line)))


# ---------------------------------------------------------------------------
# World Locations
# ---------------------------------------------------------------------------


def _location_to_dict(loc: WorldLocation) -> dict:
    return {
        "id": loc.id,
        "world_id": loc.world_id,
        "name": loc.name,
        "content": loc.content,
        "exits": loc.exits,
        "created_at": _serialize_datetime(loc.created_at),
        "modified_at": _serialize_datetime(loc.modified_at),
    }


def _dict_to_location(d: dict) -> WorldLocation:
    return WorldLocation(
        id=d["id"],
        world_id=d["world_id"],
        name=d.get("name", ""),
        content=d.get("content", ""),
        exits=d.get("exits"),
        created_at=_parse_datetime(d.get("created_at")),
        modified_at=_parse_datetime(d.get("modified_at")),
    )


async def export_world_locations(session: AsyncSession) -> bytes:
    result = await session.execute(select(WorldLocation))
    items = result.scalars().all()
    lines = "\n".join(json.dumps(_location_to_dict(i)) for i in items)
    return gzip.compress(lines.encode("utf-8"))


async def import_world_locations(session: AsyncSession, data: bytes) -> None:
    raw = gzip.decompress(data).decode("utf-8")
    for line in raw.strip().split("\n"):
        if not line:
            continue
        session.add(_dict_to_location(json.loads(line)))


# ---------------------------------------------------------------------------
# World NPCs
# ---------------------------------------------------------------------------


def _npc_to_dict(npc: WorldNPC) -> dict:
    return {
        "id": npc.id,
        "world_id": npc.world_id,
        "name": npc.name,
        "content": npc.content,
        "created_at": _serialize_datetime(npc.created_at),
        "modified_at": _serialize_datetime(npc.modified_at),
    }


def _dict_to_npc(d: dict) -> WorldNPC:
    return WorldNPC(
        id=d["id"],
        world_id=d["world_id"],
        name=d.get("name", ""),
        content=d.get("content", ""),
        created_at=_parse_datetime(d.get("created_at")),
        modified_at=_parse_datetime(d.get("modified_at")),
    )


async def export_world_npcs(session: AsyncSession) -> bytes:
    result = await session.execute(select(WorldNPC))
    items = result.scalars().all()
    lines = "\n".join(json.dumps(_npc_to_dict(i)) for i in items)
    return gzip.compress(lines.encode("utf-8"))


async def import_world_npcs(session: AsyncSession, data: bytes) -> None:
    raw = gzip.decompress(data).decode("utf-8")
    for line in raw.strip().split("\n"):
        if not line:
            continue
        session.add(_dict_to_npc(json.loads(line)))


# ---------------------------------------------------------------------------
# World Lore Facts
# ---------------------------------------------------------------------------


def _lore_fact_to_dict(fact: WorldLoreFact) -> dict:
    return {
        "id": fact.id,
        "world_id": fact.world_id,
        "content": fact.content,
        "created_at": _serialize_datetime(fact.created_at),
        "modified_at": _serialize_datetime(fact.modified_at),
    }


def _dict_to_lore_fact(d: dict) -> WorldLoreFact:
    return WorldLoreFact(
        id=d["id"],
        world_id=d["world_id"],
        content=d.get("content", ""),
        created_at=_parse_datetime(d.get("created_at")),
        modified_at=_parse_datetime(d.get("modified_at")),
    )


async def export_world_lore_facts(session: AsyncSession) -> bytes:
    result = await session.execute(select(WorldLoreFact))
    items = result.scalars().all()
    lines = "\n".join(json.dumps(_lore_fact_to_dict(i)) for i in items)
    return gzip.compress(lines.encode("utf-8"))


async def import_world_lore_facts(session: AsyncSession, data: bytes) -> None:
    raw = gzip.decompress(data).decode("utf-8")
    for line in raw.strip().split("\n"):
        if not line:
            continue
        session.add(_dict_to_lore_fact(json.loads(line)))


# ---------------------------------------------------------------------------
# NPC Location Links
# ---------------------------------------------------------------------------


def _npc_link_to_dict(link: NPCLocationLink) -> dict:
    return {
        "id": link.id,
        "npc_id": link.npc_id,
        "location_id": link.location_id,
        "link_type": link.link_type.value,
    }


def _dict_to_npc_link(d: dict) -> NPCLocationLink:
    return NPCLocationLink(
        id=d["id"],
        npc_id=d["npc_id"],
        location_id=d["location_id"],
        link_type=NPCLinkType(d["link_type"]),
    )


async def export_npc_location_links(session: AsyncSession) -> bytes:
    result = await session.execute(select(NPCLocationLink))
    items = result.scalars().all()
    lines = "\n".join(json.dumps(_npc_link_to_dict(i)) for i in items)
    return gzip.compress(lines.encode("utf-8"))


async def import_npc_location_links(session: AsyncSession, data: bytes) -> None:
    raw = gzip.decompress(data).decode("utf-8")
    for line in raw.strip().split("\n"):
        if not line:
            continue
        session.add(_dict_to_npc_link(json.loads(line)))


# ---------------------------------------------------------------------------
# World Stat Definitions
# ---------------------------------------------------------------------------


def _stat_def_to_dict(sd: WorldStatDefinition) -> dict:
    return {
        "id": sd.id,
        "world_id": sd.world_id,
        "name": sd.name,
        "description": sd.description,
        "scope": sd.scope.value,
        "stat_type": sd.stat_type.value,
        "default_value": sd.default_value,
        "min_value": sd.min_value,
        "max_value": sd.max_value,
        "enum_values": sd.enum_values,
    }


def _dict_to_stat_def(d: dict) -> WorldStatDefinition:
    return WorldStatDefinition(
        id=d["id"],
        world_id=d["world_id"],
        name=d.get("name", ""),
        description=d.get("description", ""),
        scope=StatScope(d["scope"]),
        stat_type=StatType(d["stat_type"]),
        default_value=d.get("default_value", "0"),
        min_value=d.get("min_value"),
        max_value=d.get("max_value"),
        enum_values=d.get("enum_values"),
    )


async def export_world_stat_definitions(session: AsyncSession) -> bytes:
    result = await session.execute(select(WorldStatDefinition))
    items = result.scalars().all()
    lines = "\n".join(json.dumps(_stat_def_to_dict(i)) for i in items)
    return gzip.compress(lines.encode("utf-8"))


async def import_world_stat_definitions(session: AsyncSession, data: bytes) -> None:
    raw = gzip.decompress(data).decode("utf-8")
    for line in raw.strip().split("\n"):
        if not line:
            continue
        session.add(_dict_to_stat_def(json.loads(line)))


# ---------------------------------------------------------------------------
# World Rules
# ---------------------------------------------------------------------------


def _rule_to_dict(rule: WorldRule) -> dict:
    return {
        "id": rule.id,
        "world_id": rule.world_id,
        "rule_text": rule.rule_text,
        "order": rule.order,
    }


def _dict_to_rule(d: dict) -> WorldRule:
    return WorldRule(
        id=d["id"],
        world_id=d["world_id"],
        rule_text=d.get("rule_text", ""),
        order=d.get("order", 0),
    )


async def export_world_rules(session: AsyncSession) -> bytes:
    result = await session.execute(select(WorldRule))
    items = result.scalars().all()
    lines = "\n".join(json.dumps(_rule_to_dict(i)) for i in items)
    return gzip.compress(lines.encode("utf-8"))


async def import_world_rules(session: AsyncSession, data: bytes) -> None:
    raw = gzip.decompress(data).decode("utf-8")
    for line in raw.strip().split("\n"):
        if not line:
            continue
        session.add(_dict_to_rule(json.loads(line)))


# ---------------------------------------------------------------------------
# Aggregate export / import
# ---------------------------------------------------------------------------

_EXPORT_TABLE_MAP = [
    ("users.jsonl.gz", export_users),
    ("worlds.jsonl.gz", export_worlds),
    ("world_locations.jsonl.gz", export_world_locations),
    ("world_npcs.jsonl.gz", export_world_npcs),
    ("world_lore_facts.jsonl.gz", export_world_lore_facts),
    ("npc_location_links.jsonl.gz", export_npc_location_links),
    ("world_stat_definitions.jsonl.gz", export_world_stat_definitions),
    ("world_rules.jsonl.gz", export_world_rules),
]

# Import order respects FK dependencies
_IMPORT_TABLE_MAP = [
    ("users.jsonl.gz", import_users),
    ("worlds.jsonl.gz", import_worlds),
    ("world_locations.jsonl.gz", import_world_locations),
    ("world_npcs.jsonl.gz", import_world_npcs),
    ("world_lore_facts.jsonl.gz", import_world_lore_facts),
    ("npc_location_links.jsonl.gz", import_npc_location_links),
    ("world_stat_definitions.jsonl.gz", import_world_stat_definitions),
    ("world_rules.jsonl.gz", import_world_rules),
]


async def export_all(session: AsyncSession) -> bytes:
    """Export all tables to a zip containing .jsonl.gz files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for filename, export_fn in _EXPORT_TABLE_MAP:
            data = await export_fn(session)
            zf.writestr(filename, data)
    return buf.getvalue()


async def import_all(session: AsyncSession, zip_data: bytes) -> None:
    """Import all tables from a zip of .jsonl.gz files."""
    buf = io.BytesIO(zip_data)
    with zipfile.ZipFile(buf, "r") as zf:
        names = zf.namelist()
        for filename, import_fn in _IMPORT_TABLE_MAP:
            if filename in names:
                await import_fn(session, zf.read(filename))
