"""Import/export serialization — gzipped JSONL per table in a zip archive.

This is format/serialization logic (services layer). DB access is delegated
to db.import_export_queries which manages its own sessions.
"""

import gzip
import io
import json
import logging
import zipfile
from datetime import datetime

from app.db.import_export_queries import export_table, upsert_batch
from app.models.llm_server import LlmServer
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

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


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


# ---------------------------------------------------------------------------
# LLM Servers
# ---------------------------------------------------------------------------


def _llm_server_to_dict(s: LlmServer) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "backend_type": s.backend_type,
        "base_url": s.base_url,
        "api_key": s.api_key,
        "enabled_models": s.enabled_models,
        "is_active": s.is_active,
        "is_embedding": s.is_embedding,
        "embedding_model": s.embedding_model,
        "created_at": _serialize_datetime(s.created_at),
        "modified_at": _serialize_datetime(s.modified_at),
    }


def _dict_to_llm_server(d: dict) -> LlmServer:
    return LlmServer(
        id=d["id"],
        name=d["name"],
        backend_type=d["backend_type"],
        base_url=d["base_url"],
        api_key=d.get("api_key"),
        enabled_models=d.get("enabled_models", "[]"),
        is_active=d.get("is_active", True),
        is_embedding=d.get("is_embedding", False),
        embedding_model=d.get("embedding_model"),
        created_at=_parse_datetime(d.get("created_at")),
        modified_at=_parse_datetime(d.get("modified_at")),
    )


# ---------------------------------------------------------------------------
# Table registry: (zip_filename, model_class, to_dict, from_dict)
# Import order respects FK dependencies.
# ---------------------------------------------------------------------------

TABLE_REGISTRY = [
    ("users", User, _user_to_dict, _dict_to_user),
    ("llm_servers", LlmServer, _llm_server_to_dict, _dict_to_llm_server),
    ("worlds", World, _world_to_dict, _dict_to_world),
    ("world_locations", WorldLocation, _location_to_dict, _dict_to_location),
    ("world_npcs", WorldNPC, _npc_to_dict, _dict_to_npc),
    ("world_lore_facts", WorldLoreFact, _lore_fact_to_dict, _dict_to_lore_fact),
    ("npc_location_links", NPCLocationLink, _npc_link_to_dict, _dict_to_npc_link),
    ("world_stat_definitions", WorldStatDefinition, _stat_def_to_dict, _dict_to_stat_def),
    ("world_rules", WorldRule, _rule_to_dict, _dict_to_rule),
]


# ---------------------------------------------------------------------------
# Streaming export
# ---------------------------------------------------------------------------


async def export_all() -> bytes:
    """Export all tables to a zip containing .jsonl.gz files.

    Uses streaming callback — rows are serialized one at a time into the
    gzip stream, never collected into a large in-memory list.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for table_name, model_class, to_dict_fn, _ in TABLE_REGISTRY:
            gz_buf = io.BytesIO()
            gz = gzip.open(gz_buf, "wt", encoding="utf-8")

            def make_writer(gz_file: io.TextIOWrapper, serializer):  # noqa: E301
                def write_row(row):
                    gz_file.write(json.dumps(serializer(row)) + "\n")
                return write_row

            await export_table(model_class, make_writer(gz, to_dict_fn))
            gz.close()
            zf.writestr(f"{table_name}.jsonl.gz", gz_buf.getvalue())

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Streaming import
# ---------------------------------------------------------------------------


async def import_all(zip_data: bytes) -> None:
    """Import all tables from a zip of .jsonl.gz files.

    Streams JSONL line-by-line, sends batched upserts to the db layer.
    Tables are created/reshaped via init_db() before upserting.
    """
    from app.db.engine import init_db

    await init_db()

    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zf:
        names = zf.namelist()
        for table_name, _, _, from_dict_fn in TABLE_REGISTRY:
            filename = f"{table_name}.jsonl.gz"
            if filename not in names:
                continue

            batch = []
            with gzip.open(io.BytesIO(zf.read(filename)), "rt", encoding="utf-8") as gz:
                for line in gz:
                    line = line.strip()
                    if not line:
                        continue
                    batch.append(from_dict_fn(json.loads(line)))
                    if len(batch) >= BATCH_SIZE:
                        await upsert_batch(batch)
                        batch.clear()
            if batch:
                await upsert_batch(batch)
