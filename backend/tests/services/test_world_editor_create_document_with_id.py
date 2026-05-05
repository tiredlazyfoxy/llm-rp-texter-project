"""Tests for `world_editor.create_document` honoring the optional client-supplied
`id` field in `CreateDocumentRequest`."""

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.db import locations as locations_db
from app.db import lore_facts as lore_facts_db
from app.db import npcs as npcs_db
from app.db import worlds as worlds_db
from app.models.schemas.worlds import CreateDocumentRequest
from app.models.world import (
    World,
    WorldLocation,
    WorldLoreFact,
    WorldNPC,
    WorldStatus,
)
from app.services import world_editor
from app.services.snowflake import generate_id


pytestmark = pytest.mark.asyncio


async def _make_world() -> int:
    world = World(
        id=generate_id(),
        name=f"test-world-{generate_id()}",
        description="",
        lore="",
        character_template="",
        initial_message="",
        status=WorldStatus.draft,
        owner_id=None,
        created_at=datetime.now(timezone.utc),
        modified_at=datetime.now(timezone.utc),
    )
    await worlds_db.create(world)
    return world.id


# ── Regression: req.id = None still works ──────────────────────────

async def test_create_document_without_id_generates_one() -> None:
    world_id = await _make_world()
    req = CreateDocumentRequest(doc_type="location", name="Tavern", content="A tavern.")
    result = await world_editor.create_document(world_id, req)

    assert result["doc_type"] == "location"
    assert result["obj"].id is not None
    assert result["obj"].id > 0


# ── Success: req.id supplied with unused snowflake ─────────────────

async def test_create_document_with_unused_id_uses_it_for_location() -> None:
    world_id = await _make_world()
    chosen_id = generate_id()
    req = CreateDocumentRequest(
        doc_type="location", name="Throne Room", content="...", id=str(chosen_id),
    )
    result = await world_editor.create_document(world_id, req)

    assert result["obj"].id == chosen_id
    # Persisted with that id
    fetched = await locations_db.get_by_id(chosen_id)
    assert fetched is not None
    assert fetched.id == chosen_id


async def test_create_document_with_unused_id_uses_it_for_npc() -> None:
    world_id = await _make_world()
    chosen_id = generate_id()
    req = CreateDocumentRequest(
        doc_type="npc", name="Goblin", content="A goblin.", id=str(chosen_id),
    )
    result = await world_editor.create_document(world_id, req)

    assert result["obj"].id == chosen_id
    fetched = await npcs_db.get_by_id(chosen_id)
    assert fetched is not None


async def test_create_document_with_unused_id_uses_it_for_lore_fact() -> None:
    world_id = await _make_world()
    chosen_id = generate_id()
    req = CreateDocumentRequest(
        doc_type="lore_fact", content="The world is round.", id=str(chosen_id),
    )
    result = await world_editor.create_document(world_id, req)

    assert result["obj"].id == chosen_id
    fetched = await lore_facts_db.get_by_id(chosen_id)
    assert fetched is not None


# ── Collision: 409 across all three tables ─────────────────────────

async def test_create_document_with_id_colliding_with_location_returns_409() -> None:
    world_id = await _make_world()
    existing_id = generate_id()
    now = datetime.now(timezone.utc)
    await locations_db.create(WorldLocation(
        id=existing_id, world_id=world_id, name="Existing",
        content="", created_at=now, modified_at=now,
    ))

    req = CreateDocumentRequest(
        doc_type="npc", name="New", content="", id=str(existing_id),
    )
    with pytest.raises(HTTPException) as exc_info:
        await world_editor.create_document(world_id, req)
    assert exc_info.value.status_code == 409


async def test_create_document_with_id_colliding_with_npc_returns_409() -> None:
    world_id = await _make_world()
    existing_id = generate_id()
    now = datetime.now(timezone.utc)
    await npcs_db.create(WorldNPC(
        id=existing_id, world_id=world_id, name="Existing",
        content="", created_at=now, modified_at=now,
    ))

    req = CreateDocumentRequest(
        doc_type="lore_fact", content="x", id=str(existing_id),
    )
    with pytest.raises(HTTPException) as exc_info:
        await world_editor.create_document(world_id, req)
    assert exc_info.value.status_code == 409


async def test_create_document_with_id_colliding_with_lore_fact_returns_409() -> None:
    world_id = await _make_world()
    existing_id = generate_id()
    now = datetime.now(timezone.utc)
    await lore_facts_db.create(WorldLoreFact(
        id=existing_id, world_id=world_id, content="x",
        created_at=now, modified_at=now,
    ))

    req = CreateDocumentRequest(
        doc_type="location", name="New", content="", id=str(existing_id),
    )
    with pytest.raises(HTTPException) as exc_info:
        await world_editor.create_document(world_id, req)
    assert exc_info.value.status_code == 409


# ── Invalid id strings: 4xx (not 500) ──────────────────────────────

async def test_create_document_with_non_numeric_id_returns_4xx() -> None:
    world_id = await _make_world()
    req = CreateDocumentRequest(
        doc_type="location", name="Bad id", content="", id="not-a-number",
    )
    with pytest.raises(HTTPException) as exc_info:
        await world_editor.create_document(world_id, req)
    # Service raises 400 for bad id; ensure it's a 4xx, not a 500.
    assert 400 <= exc_info.value.status_code < 500


# ── document_id_exists DB helper basic sanity ──────────────────────

async def test_document_id_exists_returns_false_for_unused_id() -> None:
    unused = generate_id()
    assert await worlds_db.document_id_exists(unused) is False


async def test_document_id_exists_returns_true_after_insert() -> None:
    world_id = await _make_world()
    chosen_id = generate_id()
    now = datetime.now(timezone.utc)
    await npcs_db.create(WorldNPC(
        id=chosen_id, world_id=world_id, name="x",
        content="", created_at=now, modified_at=now,
    ))
    assert await worlds_db.document_id_exists(chosen_id) is True
