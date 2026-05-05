"""Tests for GET /api/admin/snowflake/new."""

from typing import Tuple

import pytest

from app.models.user import User


pytestmark = pytest.mark.asyncio


async def test_returns_id_when_authenticated(
    http_client, editor_user: Tuple[User, str]
) -> None:
    _, token = editor_user
    resp = await http_client.get(
        "/api/admin/snowflake/new",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
    assert isinstance(body["id"], str)
    # Numeric snowflake string
    assert body["id"].isdigit()
    assert int(body["id"]) > 0


async def test_unauthenticated_returns_401_or_403(http_client) -> None:
    resp = await http_client.get("/api/admin/snowflake/new")
    # No auth header at all — HTTPBearer raises 403 by default in FastAPI
    assert resp.status_code in (401, 403)


async def test_player_role_forbidden(
    http_client, player_user: Tuple[User, str]
) -> None:
    _, token = player_user
    resp = await http_client.get(
        "/api/admin/snowflake/new",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_two_consecutive_calls_return_distinct_ids(
    http_client, editor_user: Tuple[User, str]
) -> None:
    _, token = editor_user
    headers = {"Authorization": f"Bearer {token}"}
    r1 = await http_client.get("/api/admin/snowflake/new", headers=headers)
    r2 = await http_client.get("/api/admin/snowflake/new", headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] != r2.json()["id"]
