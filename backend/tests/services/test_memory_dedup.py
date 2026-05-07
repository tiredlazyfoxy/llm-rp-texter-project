"""Tests for the memory_compaction service and the ChatMemory `embedding`
column round-trip through JSONL import/export.

Covers fast feature 001 (memory_dedup):
- dedup happy path (new vs existing)
- dedup new-vs-new (within one run)
- threshold boundary (just-below threshold keeps both)
- no embedding server (skipped result, no DB writes)
- import/export round-trip including absent-key compatibility
"""

import json
from datetime import datetime, timezone

import pytest

from app.db import chats as chats_db
from app.models.chat_memory import ChatMemory
from app.services import memory_compaction
from app.services.db_import_export import (
    _chat_memory_to_dict,
    _dict_to_chat_memory,
)
from app.services.memory_compaction import (
    MEMORY_DEDUP_COSINE_THRESHOLD,
    compact_new_memories,
)
from app.services.snowflake import generate_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _create_memory(
    session_id: int,
    content: str,
    embedding: list[float] | None = None,
) -> int:
    mem = ChatMemory(
        id=generate_id(),
        session_id=session_id,
        content=content,
        created_at=_now(),
        embedding=embedding,
    )
    await chats_db.create_memory(mem)
    return mem.id


def _patch_embedding(
    monkeypatch: pytest.MonkeyPatch,
    *,
    configured: bool,
    vectors: dict[str, list[float]] | None = None,
) -> list[list[str]]:
    """Patch is_embedding_configured / embed_texts inside memory_compaction.

    Returns a list capturing each batch of texts passed to embed_texts so
    tests can assert on call shape (single batch, etc.).
    """
    calls: list[list[str]] = []

    async def _is_configured() -> bool:
        return configured

    async def _embed(texts: list[str]) -> list[list[float]]:
        calls.append(list(texts))
        if vectors is None:
            raise AssertionError("embed_texts called but no vectors stub provided")
        return [vectors[t] for t in texts]

    monkeypatch.setattr(memory_compaction, "is_embedding_configured", _is_configured)
    monkeypatch.setattr(memory_compaction, "embed_texts", _embed)
    return calls


# ---------------------------------------------------------------------------
# Cosine helper
# ---------------------------------------------------------------------------


def test_cosine_zero_norm_returns_zero() -> None:
    assert memory_compaction._cosine([0.0, 0.0], [1.0, 0.0]) == 0.0
    assert memory_compaction._cosine([1.0, 0.0], [0.0, 0.0]) == 0.0
    assert memory_compaction._cosine([], [1.0]) == 0.0
    assert memory_compaction._cosine([1.0, 0.0], [1.0]) == 0.0


def test_cosine_identical_is_one() -> None:
    sim = memory_compaction._cosine([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    assert abs(sim - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# compact_new_memories — happy paths
# ---------------------------------------------------------------------------


async def test_compaction_drops_new_duplicate_of_existing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = generate_id()

    # Pre-existing memory with NO embedding (lazy-backfill path).
    existing_id = await _create_memory(session_id, "User likes apples.")
    # New memory added this run, near-duplicate.
    new_id = await _create_memory(session_id, "The user loves apples.")

    vectors = {
        "User likes apples.": [1.0, 0.0, 0.0],
        "The user loves apples.": [0.99, 0.01, 0.0],  # cosine ~ 0.99995 -> drop
    }
    calls = _patch_embedding(monkeypatch, configured=True, vectors=vectors)

    result = await compact_new_memories(session_id, [new_id])

    # Single batched embed call covering both rows.
    assert len(calls) == 1
    assert sorted(calls[0]) == sorted([
        "User likes apples.", "The user loves apples.",
    ])

    assert result.skipped is False
    assert [d.id for d in result.dropped] == [new_id]
    assert result.dropped[0].duplicate_of_id == existing_id
    assert result.dropped[0].similarity >= MEMORY_DEDUP_COSINE_THRESHOLD
    assert result.kept == []

    # DB state: new row gone, existing row still there with embedding persisted.
    remaining = await chats_db.list_memories(session_id)
    assert [m.id for m in remaining] == [existing_id]
    assert remaining[0].embedding == vectors["User likes apples."]


async def test_compaction_drops_new_vs_new(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = generate_id()

    # Two new memories, near-duplicate of each other; first wins.
    first_id = await _create_memory(session_id, "Met the librarian today.")
    second_id = await _create_memory(session_id, "Today I met the librarian.")
    assert first_id < second_id  # snowflake monotonic — first added wins ties

    vectors = {
        "Met the librarian today.": [1.0, 0.0, 0.0],
        "Today I met the librarian.": [0.98, 0.02, 0.0],
    }
    _patch_embedding(monkeypatch, configured=True, vectors=vectors)

    result = await compact_new_memories(session_id, [first_id, second_id])

    assert result.skipped is False
    assert [m.id for m in result.kept] == [first_id]
    assert [d.id for d in result.dropped] == [second_id]
    assert result.dropped[0].duplicate_of_id == first_id

    remaining = await chats_db.list_memories(session_id)
    assert [m.id for m in remaining] == [first_id]
    assert remaining[0].embedding == vectors["Met the librarian today."]


async def test_compaction_threshold_boundary_keeps_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = generate_id()

    a_id = await _create_memory(session_id, "Knows about herbs.")
    b_id = await _create_memory(session_id, "Skilled with mushrooms.")

    # Cosine of (1,0) and (0.91, sqrt(1-0.91^2)) is exactly 0.91 — below 0.92.
    import math
    other = math.sqrt(1.0 - 0.91 * 0.91)
    vectors = {
        "Knows about herbs.": [1.0, 0.0],
        "Skilled with mushrooms.": [0.91, other],
    }
    _patch_embedding(monkeypatch, configured=True, vectors=vectors)

    result = await compact_new_memories(session_id, [a_id, b_id])

    assert result.skipped is False
    assert result.dropped == []
    assert sorted(m.id for m in result.kept) == sorted([a_id, b_id])

    remaining = await chats_db.list_memories(session_id)
    assert sorted(m.id for m in remaining) == sorted([a_id, b_id])


# ---------------------------------------------------------------------------
# Skip behaviors
# ---------------------------------------------------------------------------


async def test_compaction_skipped_when_no_embedding_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = generate_id()
    new_id = await _create_memory(session_id, "Should remain untouched.")

    _patch_embedding(monkeypatch, configured=False, vectors=None)

    result = await compact_new_memories(session_id, [new_id])

    assert result.skipped is True
    assert result.skip_reason == "no_embedding_server"
    assert result.kept == []
    assert result.dropped == []

    # Nothing written, nothing deleted.
    remaining = await chats_db.list_memories(session_id)
    assert [m.id for m in remaining] == [new_id]
    assert remaining[0].embedding is None


async def test_compaction_skipped_when_no_new_ids() -> None:
    session_id = generate_id()
    result = await compact_new_memories(session_id, [])
    assert result.skipped is True
    assert result.skip_reason == "no_new_memories"
    assert result.kept == []
    assert result.dropped == []


# ---------------------------------------------------------------------------
# Import/export round-trip
# ---------------------------------------------------------------------------


def test_chat_memory_dict_round_trip_with_embedding() -> None:
    mem = ChatMemory(
        id=generate_id(),
        session_id=generate_id(),
        content="something",
        created_at=_now(),
        embedding=[0.1, 0.2, 0.3],
    )
    d = _chat_memory_to_dict(mem)
    assert d["embedding"] == [0.1, 0.2, 0.3]

    # Survives a JSON serialization round-trip (export writes JSONL).
    raw = json.dumps(d)
    parsed = json.loads(raw)
    restored = _dict_to_chat_memory(parsed)
    assert restored.embedding == [0.1, 0.2, 0.3]


def test_chat_memory_dict_round_trip_with_none_embedding() -> None:
    mem = ChatMemory(
        id=generate_id(),
        session_id=generate_id(),
        content="bare",
        created_at=_now(),
        embedding=None,
    )
    d = _chat_memory_to_dict(mem)
    assert d["embedding"] is None

    restored = _dict_to_chat_memory(json.loads(json.dumps(d)))
    assert restored.embedding is None


def test_chat_memory_import_legacy_export_without_embedding_key() -> None:
    # Old export format predating the embedding column.
    legacy = {
        "id": generate_id(),
        "session_id": generate_id(),
        "content": "old data",
        "created_at": _now().isoformat(),
    }
    restored = _dict_to_chat_memory(legacy)
    assert restored.embedding is None
    assert restored.content == "old data"
