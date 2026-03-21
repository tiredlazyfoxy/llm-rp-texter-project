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
from app.models.chat_memory import ChatMemory
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.chat_state_snapshot import ChatStateSnapshot
from app.models.chat_summary import ChatSummary
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
        "generation_mode": w.generation_mode,
        "agent_config": w.agent_config,
        "status": w.status.value,
        "owner_id": w.owner_id,
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
        generation_mode=d.get("generation_mode", "simple"),
        agent_config=d.get("agent_config", "{}"),
        status=WorldStatus(d["status"]),
        owner_id=d.get("owner_id"),
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
        "is_injected": fact.is_injected,
        "weight": fact.weight,
        "created_at": _serialize_datetime(fact.created_at),
        "modified_at": _serialize_datetime(fact.modified_at),
    }


def _dict_to_lore_fact(d: dict) -> WorldLoreFact:
    return WorldLoreFact(
        id=d["id"],
        world_id=d["world_id"],
        content=d.get("content", ""),
        is_injected=d.get("is_injected", False),
        weight=d.get("weight", 0),
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
        "hidden": sd.hidden,
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
        hidden=d.get("hidden", False),
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

# ---------------------------------------------------------------------------
# Chat Sessions
# ---------------------------------------------------------------------------


def _chat_session_to_dict(s: ChatSession) -> dict:
    return {
        "id": s.id,
        "user_id": s.user_id,
        "world_id": s.world_id,
        "current_location_id": s.current_location_id,
        "character_name": s.character_name,
        "character_description": s.character_description,
        "character_stats": s.character_stats,
        "world_stats": s.world_stats,
        "current_turn": s.current_turn,
        "status": s.status,
        "tool_model_id": s.tool_model_id,
        "tool_temperature": s.tool_temperature,
        "tool_repeat_penalty": s.tool_repeat_penalty,
        "tool_top_p": s.tool_top_p,
        "text_model_id": s.text_model_id,
        "text_temperature": s.text_temperature,
        "text_repeat_penalty": s.text_repeat_penalty,
        "text_top_p": s.text_top_p,
        "user_instructions": s.user_instructions,
        "created_at": _serialize_datetime(s.created_at),
        "modified_at": _serialize_datetime(s.modified_at),
    }


def _dict_to_chat_session(d: dict) -> ChatSession:
    return ChatSession(
        id=d["id"],
        user_id=d["user_id"],
        world_id=d["world_id"],
        current_location_id=d.get("current_location_id"),
        character_name=d["character_name"],
        character_description=d.get("character_description", ""),
        character_stats=d.get("character_stats", "{}"),
        world_stats=d.get("world_stats", "{}"),
        current_turn=d.get("current_turn", 0),
        status=d.get("status", "active"),
        tool_model_id=d.get("tool_model_id"),
        tool_temperature=d.get("tool_temperature", 0.7),
        tool_repeat_penalty=d.get("tool_repeat_penalty", 1.0),
        tool_top_p=d.get("tool_top_p", 1.0),
        text_model_id=d.get("text_model_id"),
        text_temperature=d.get("text_temperature", 0.7),
        text_repeat_penalty=d.get("text_repeat_penalty", 1.0),
        text_top_p=d.get("text_top_p", 1.0),
        user_instructions=d.get("user_instructions", ""),
        created_at=_parse_datetime(d.get("created_at")),
        modified_at=_parse_datetime(d.get("modified_at")),
    )


# ---------------------------------------------------------------------------
# Chat Summaries
# ---------------------------------------------------------------------------


def _chat_summary_to_dict(s: ChatSummary) -> dict:
    return {
        "id": s.id,
        "session_id": s.session_id,
        "start_message_id": s.start_message_id,
        "end_message_id": s.end_message_id,
        "start_turn": s.start_turn,
        "end_turn": s.end_turn,
        "content": s.content,
        "created_at": _serialize_datetime(s.created_at),
    }


def _dict_to_chat_summary(d: dict) -> ChatSummary:
    return ChatSummary(
        id=d["id"],
        session_id=d["session_id"],
        start_message_id=d["start_message_id"],
        end_message_id=d["end_message_id"],
        start_turn=d["start_turn"],
        end_turn=d["end_turn"],
        content=d.get("content", ""),
        created_at=_parse_datetime(d.get("created_at")),
    )


# ---------------------------------------------------------------------------
# Chat Messages
# ---------------------------------------------------------------------------


def _chat_message_to_dict(m: ChatMessage) -> dict:
    return {
        "id": m.id,
        "session_id": m.session_id,
        "role": m.role,
        "content": m.content,
        "turn_number": m.turn_number,
        "tool_calls": m.tool_calls,
        "generation_plan": m.generation_plan,
        "summary_id": m.summary_id,
        "is_active_variant": m.is_active_variant,
        "created_at": _serialize_datetime(m.created_at),
    }


def _dict_to_chat_message(d: dict) -> ChatMessage:
    return ChatMessage(
        id=d["id"],
        session_id=d["session_id"],
        role=d["role"],
        content=d.get("content", ""),
        turn_number=d["turn_number"],
        tool_calls=d.get("tool_calls"),
        generation_plan=d.get("generation_plan"),
        summary_id=d.get("summary_id"),
        is_active_variant=d.get("is_active_variant", True),
        created_at=_parse_datetime(d.get("created_at")),
    )


# ---------------------------------------------------------------------------
# Chat State Snapshots
# ---------------------------------------------------------------------------


def _chat_state_snapshot_to_dict(s: ChatStateSnapshot) -> dict:
    return {
        "id": s.id,
        "session_id": s.session_id,
        "turn_number": s.turn_number,
        "location_id": s.location_id,
        "character_stats": s.character_stats,
        "world_stats": s.world_stats,
        "created_at": _serialize_datetime(s.created_at),
    }


def _dict_to_chat_state_snapshot(d: dict) -> ChatStateSnapshot:
    return ChatStateSnapshot(
        id=d["id"],
        session_id=d["session_id"],
        turn_number=d["turn_number"],
        location_id=d.get("location_id"),
        character_stats=d.get("character_stats", "{}"),
        world_stats=d.get("world_stats", "{}"),
        created_at=_parse_datetime(d.get("created_at")),
    )


# ---------------------------------------------------------------------------
# Chat Memories
# ---------------------------------------------------------------------------


def _chat_memory_to_dict(m: ChatMemory) -> dict:
    return {
        "id": m.id,
        "session_id": m.session_id,
        "content": m.content,
        "created_at": _serialize_datetime(m.created_at),
    }


def _dict_to_chat_memory(d: dict) -> ChatMemory:
    return ChatMemory(
        id=d["id"],
        session_id=d["session_id"],
        content=d.get("content", ""),
        created_at=_parse_datetime(d.get("created_at")),
    )


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
    ("chat_sessions", ChatSession, _chat_session_to_dict, _dict_to_chat_session),
    ("chat_summaries", ChatSummary, _chat_summary_to_dict, _dict_to_chat_summary),
    ("chat_messages", ChatMessage, _chat_message_to_dict, _dict_to_chat_message),
    ("chat_state_snapshots", ChatStateSnapshot, _chat_state_snapshot_to_dict, _dict_to_chat_state_snapshot),
    ("chat_memories", ChatMemory, _chat_memory_to_dict, _dict_to_chat_memory),
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
