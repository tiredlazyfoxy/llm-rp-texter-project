"""Tests for `PUT /api/chats/{chat_id}/stats` — admin manual stat correction.

Feature 012, step 004. The endpoint reuses the existing
`validate_single_value` per-value validator (the same one the LLM
`update_stat` tool calls) and persists via the db layer; no SSE is
emitted (the response echoes the applied list — step 006's drawer
refreshes from that echo).
"""

import json
from datetime import datetime, timezone

import pytest

from app.db import chats as chats_db
from app.db import stat_defs as stat_defs_db
from app.db import worlds as worlds_db
from app.models.chat_session import ChatSession
from app.models.user import User
from app.models.world import (
    StatScope,
    StatType,
    World,
    WorldStatDefinition,
    WorldStatus,
)
from app.services.snowflake import generate_id


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _make_world_with_stats() -> int:
    """Create a world with one int (character), one enum (world),
    one set (character) stat. Returns world_id."""
    world = World(
        id=generate_id(),
        name=f"stats-admin-world-{generate_id()}",
        description="",
        lore="",
        character_template="",
        initial_message="",
        status=WorldStatus.public,
        owner_id=None,
        created_at=_now(),
        modified_at=_now(),
    )
    await worlds_db.create(world)

    health = WorldStatDefinition(
        id=generate_id(),
        world_id=world.id,
        name="HEALTH",
        description="",
        scope=StatScope.character,
        stat_type=StatType.int_,
        default_value="100",
        min_value=0,
        max_value=100,
        enum_values=None,
        hidden=False,
    )
    weather = WorldStatDefinition(
        id=generate_id(),
        world_id=world.id,
        name="WEATHER",
        description="",
        scope=StatScope.world,
        stat_type=StatType.enum_,
        default_value="sunny",
        min_value=None,
        max_value=None,
        enum_values=json.dumps(["sunny", "rainy", "stormy"]),
        hidden=False,
    )
    inventory = WorldStatDefinition(
        id=generate_id(),
        world_id=world.id,
        name="INVENTORY",
        description="",
        scope=StatScope.character,
        stat_type=StatType.set_,
        default_value="[]",
        min_value=None,
        max_value=None,
        enum_values=json.dumps(["sword", "shield", "potion"]),
        hidden=False,
    )
    await stat_defs_db.create(health)
    await stat_defs_db.create(weather)
    await stat_defs_db.create(inventory)

    return world.id


async def _make_chat(world_id: int, user_id: int) -> int:
    chat = ChatSession(
        id=generate_id(),
        user_id=user_id,
        world_id=world_id,
        current_location_id=None,
        character_name="Tester",
        character_description="",
        character_stats=json.dumps({"HEALTH": 100, "INVENTORY": []}),
        world_stats=json.dumps({"WEATHER": "sunny"}),
        current_turn=0,
        status="active",
        tool_model_id=None,
        text_model_id=None,
        user_instructions="",
        generation_variants="[]",
        created_at=_now(),
        modified_at=_now(),
    )
    await chats_db.create_session(chat)
    return chat.id


# ---------------------------------------------------------------------------
# 200 OK — admin + valid updates
# ---------------------------------------------------------------------------


async def test_admin_valid_updates_returns_200_and_persists(
    http_client, admin_user: tuple[User, str],
) -> None:
    admin, token = admin_user
    world_id = await _make_world_with_stats()
    chat_id = await _make_chat(world_id, admin.id)

    payload = {
        "updates": [
            {"owner": "user", "name": "HEALTH", "value": 42},
            {"owner": "world", "name": "WEATHER", "value": "rainy"},
            {"owner": "user", "name": "INVENTORY", "value": ["sword", "potion"]},
        ]
    }

    resp = await http_client.put(
        f"/api/chats/{chat_id}/stats",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["chat_id"] == str(chat_id)
    assert body["applied"] == payload["updates"]

    # Persisted on the chat row.
    chat = await chats_db.get_session_by_id(chat_id)
    assert chat is not None
    assert chats_db.parse_stats(chat.character_stats) == {
        "HEALTH": 42,
        "INVENTORY": ["sword", "potion"],
    }
    assert chats_db.parse_stats(chat.world_stats) == {"WEATHER": "rainy"}


async def test_admin_valid_int_clamps_to_min_max_and_echoes_input(
    http_client, admin_user: tuple[User, str],
) -> None:
    """Out-of-range int values are clamped on persistence (existing
    LLM-path behavior); the response echoes the *requested* update list
    — step 006 reads the persisted state from the chat detail it
    refreshes after the response."""
    admin, token = admin_user
    world_id = await _make_world_with_stats()
    chat_id = await _make_chat(world_id, admin.id)

    payload = {
        "updates": [
            {"owner": "user", "name": "HEALTH", "value": 9999},
        ]
    }
    resp = await http_client.put(
        f"/api/chats/{chat_id}/stats",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200, resp.text
    chat = await chats_db.get_session_by_id(chat_id)
    assert chat is not None
    assert chats_db.parse_stats(chat.character_stats)["HEALTH"] == 100  # clamped


# ---------------------------------------------------------------------------
# 401 / 403 — auth gating
# ---------------------------------------------------------------------------


async def test_unauthenticated_returns_401_or_403(http_client) -> None:
    # We don't even need a real chat — the auth dep fires first.
    resp = await http_client.put(
        "/api/chats/1/stats",
        json={"updates": []},
    )
    # FastAPI's HTTPBearer raises 403 by default when no header is sent.
    assert resp.status_code in (401, 403)


async def test_non_admin_player_returns_403(
    http_client, player_user: tuple[User, str],
) -> None:
    player, token = player_user
    world_id = await _make_world_with_stats()
    chat_id = await _make_chat(world_id, player.id)

    resp = await http_client.put(
        f"/api/chats/{chat_id}/stats",
        json={"updates": [{"owner": "user", "name": "HEALTH", "value": 50}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_editor_returns_200_and_persists(
    http_client, editor_user: tuple[User, str],
) -> None:
    """Editors can correct chat stats too (admin + editor are both
    accepted by the route gate; only players are denied)."""
    editor, token = editor_user
    world_id = await _make_world_with_stats()
    chat_id = await _make_chat(world_id, editor.id)

    payload = {
        "updates": [
            {"owner": "user", "name": "HEALTH", "value": 42},
            {"owner": "world", "name": "WEATHER", "value": "rainy"},
            {"owner": "user", "name": "INVENTORY", "value": ["sword", "potion"]},
        ]
    }

    resp = await http_client.put(
        f"/api/chats/{chat_id}/stats",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["chat_id"] == str(chat_id)
    assert body["applied"] == payload["updates"]

    # Persisted on the chat row.
    chat = await chats_db.get_session_by_id(chat_id)
    assert chat is not None
    assert chats_db.parse_stats(chat.character_stats) == {
        "HEALTH": 42,
        "INVENTORY": ["sword", "potion"],
    }
    assert chats_db.parse_stats(chat.world_stats) == {"WEATHER": "rainy"}


# ---------------------------------------------------------------------------
# 404 — missing chat
# ---------------------------------------------------------------------------


async def test_missing_chat_returns_404(
    http_client, admin_user: tuple[User, str],
) -> None:
    _admin, token = admin_user

    resp = await http_client.put(
        "/api/chats/999999999999/stats",
        json={"updates": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 422 — validation failures (LLM-tool-shaped error body)
# ---------------------------------------------------------------------------


async def test_value_type_mismatch_returns_422_with_llm_error_shape(
    http_client, admin_user: tuple[User, str],
) -> None:
    """An int stat receiving a non-numeric value: the helper rejects
    the value, the route raises HTTPException(422), and the body
    matches the `update_stat` tool's `{status, reason, all_stats}`
    shape (consistent admin/tool error UX)."""
    admin, token = admin_user
    world_id = await _make_world_with_stats()
    chat_id = await _make_chat(world_id, admin.id)

    resp = await http_client.put(
        f"/api/chats/{chat_id}/stats",
        json={"updates": [{"owner": "user", "name": "HEALTH", "value": "not-a-number"}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    body = resp.json()
    detail = body["detail"]
    assert detail["status"] == "ERROR"
    assert "HEALTH" in detail["reason"]
    assert "all_stats" in detail
    # Snapshot reflects pre-update state (admin endpoint is all-or-nothing).
    assert detail["all_stats"]["HEALTH"] == "100"


async def test_enum_value_outside_allowed_returns_422_with_llm_error_shape(
    http_client, admin_user: tuple[User, str],
) -> None:
    admin, token = admin_user
    world_id = await _make_world_with_stats()
    chat_id = await _make_chat(world_id, admin.id)

    resp = await http_client.put(
        f"/api/chats/{chat_id}/stats",
        json={"updates": [{"owner": "world", "name": "WEATHER", "value": "snowing"}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["status"] == "ERROR"
    assert "WEATHER" in detail["reason"]


async def test_invalid_stat_name_returns_llm_tool_error_shape(
    http_client, admin_user: tuple[User, str],
) -> None:
    """An unknown stat name surfaces the *same* error shape as the
    LLM `update_stat` tool: status=ERROR, reason mentions the bad
    name and lists the valid ones, plus an all_stats snapshot.
    Verified against the tool body shape in chat_tools._b_update_stat."""
    admin, token = admin_user
    world_id = await _make_world_with_stats()
    chat_id = await _make_chat(world_id, admin.id)

    resp = await http_client.put(
        f"/api/chats/{chat_id}/stats",
        json={"updates": [{"owner": "user", "name": "MOOD", "value": 10}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["status"] == "ERROR"
    assert "MOOD" in detail["reason"]
    assert "not recognized" in detail["reason"]
    # Body shape parity with LLM tool error: must include all_stats key.
    assert "all_stats" in detail
    # No partial application — chat row is unchanged.
    chat = await chats_db.get_session_by_id(chat_id)
    assert chat is not None
    assert chats_db.parse_stats(chat.character_stats) == {"HEALTH": 100, "INVENTORY": []}
    assert chats_db.parse_stats(chat.world_stats) == {"WEATHER": "sunny"}


async def test_owner_mismatch_returns_422(
    http_client, admin_user: tuple[User, str],
) -> None:
    """Owner namespace must match the stat's scope: HEALTH is a
    character (user) stat — declaring owner=world rejects."""
    admin, token = admin_user
    world_id = await _make_world_with_stats()
    chat_id = await _make_chat(world_id, admin.id)

    resp = await http_client.put(
        f"/api/chats/{chat_id}/stats",
        json={"updates": [{"owner": "world", "name": "HEALTH", "value": 50}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["status"] == "ERROR"
    assert "HEALTH" in detail["reason"]


async def test_request_body_pydantic_validation_returns_422(
    http_client, admin_user: tuple[User, str],
) -> None:
    """Sending a payload with the wrong literal owner value is
    rejected by the Pydantic schema before the service runs (FastAPI
    422). Confirms the request schema is strictly typed."""
    admin, token = admin_user
    world_id = await _make_world_with_stats()
    chat_id = await _make_chat(world_id, admin.id)

    resp = await http_client.put(
        f"/api/chats/{chat_id}/stats",
        json={"updates": [{"owner": "system", "name": "HEALTH", "value": 50}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
