"""Tests for `world_editor.upload_documents` covering all three doc types.

Focus is the `lore_fact` branch added in feature 013 step 001 — the
service previously raised HTTP 400 for that doc_type; it now bulk-creates
one new `WorldLoreFact` per uploaded file. `location` / `npc` happy paths
are exercised here as a regression guard.
"""

from datetime import datetime, timezone

import pytest

from app.db import locations as locations_db
from app.db import lore_facts as lore_facts_db
from app.db import npcs as npcs_db
from app.db import worlds as worlds_db
from app.models.world import World, WorldStatus
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


# ── lore_fact happy path ───────────────────────────────────────────

async def test_upload_lore_fact_two_files_creates_two_rows() -> None:
    world_id = await _make_world()
    files = [
        ("fact_a.md", "The world is round."),
        ("fact_b.md", "Magic is real."),
    ]
    results = await world_editor.upload_documents(world_id, files, "lore_fact")

    assert len(results) == 2
    for result, (_filename, content) in zip(results, files):
        assert result["doc_type"] == "lore_fact"
        obj = result["obj"]
        assert obj.world_id == world_id
        assert obj.content == content
        assert obj.is_injected is False
        assert obj.weight == 0
        # Lore facts have no `name` field
        assert not hasattr(obj, "name")

    # Distinct snowflake ids
    ids = [r["obj"].id for r in results]
    assert len(set(ids)) == 2


async def test_upload_lore_fact_zero_files_returns_empty_list() -> None:
    world_id = await _make_world()
    results = await world_editor.upload_documents(world_id, [], "lore_fact")
    assert results == []


async def test_upload_lore_fact_persists_rows() -> None:
    world_id = await _make_world()
    files = [
        ("alpha.md", "Alpha content."),
        ("beta.txt", "Beta content."),
    ]
    results = await world_editor.upload_documents(world_id, files, "lore_fact")

    persisted = await lore_facts_db.list_by_world(world_id)
    persisted_ids = {f.id for f in persisted}
    for r in results:
        assert r["obj"].id in persisted_ids

    contents = {f.content for f in persisted}
    assert contents == {"Alpha content.", "Beta content."}


async def test_upload_lore_fact_does_not_raise() -> None:
    """Regression guard — previously this branch raised HTTPException 400."""
    world_id = await _make_world()
    # A single-file upload should now succeed without raising.
    results = await world_editor.upload_documents(
        world_id, [("anything.md", "body")], "lore_fact",
    )
    assert len(results) == 1
    assert results[0]["doc_type"] == "lore_fact"


async def test_upload_lore_fact_each_call_creates_new_rows() -> None:
    """No upsert: re-uploading the same content always creates new rows."""
    world_id = await _make_world()
    files = [("dup.md", "Same content.")]

    first = await world_editor.upload_documents(world_id, files, "lore_fact")
    second = await world_editor.upload_documents(world_id, files, "lore_fact")

    assert first[0]["obj"].id != second[0]["obj"].id
    persisted = await lore_facts_db.list_by_world(world_id)
    assert len([f for f in persisted if f.content == "Same content."]) == 2


# ── Regression: location / npc upload still works ──────────────────

async def test_upload_location_creates_new_row() -> None:
    world_id = await _make_world()
    results = await world_editor.upload_documents(
        world_id, [("Tavern.md", "A cozy tavern.")], "location",
    )

    assert len(results) == 1
    assert results[0]["doc_type"] == "location"
    assert results[0]["obj"].name == "Tavern"
    assert results[0]["obj"].content == "A cozy tavern."
    fetched = await locations_db.get_by_id(results[0]["obj"].id)
    assert fetched is not None


async def test_upload_npc_creates_new_row() -> None:
    world_id = await _make_world()
    results = await world_editor.upload_documents(
        world_id, [("Goblin.md", "A snarling goblin.")], "npc",
    )

    assert len(results) == 1
    assert results[0]["doc_type"] == "npc"
    assert results[0]["obj"].name == "Goblin"
    fetched = await npcs_db.get_by_id(results[0]["obj"].id)
    assert fetched is not None


async def test_upload_location_upserts_by_name() -> None:
    world_id = await _make_world()
    await world_editor.upload_documents(
        world_id, [("Tavern.md", "First version.")], "location",
    )
    await world_editor.upload_documents(
        world_id, [("Tavern.md", "Second version.")], "location",
    )

    locs = await locations_db.list_by_world(world_id)
    tavern_rows = [loc for loc in locs if loc.name == "Tavern"]
    assert len(tavern_rows) == 1
    assert tavern_rows[0].content == "Second version."
