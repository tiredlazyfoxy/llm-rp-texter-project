"""Tests for inline memory deduplication (fast feature 002, memory_dedup_inline).

Covers the inline dedup guard that runs on every `add_memory` call:
- DoD-1 near-duplicate (cosine >= 0.85) is suppressed (not persisted)
- DoD-2 distinct memory (cosine < 0.85) is persisted with its embedding stored
- DoD-3 threshold is inclusive: exactly 0.85 suppressed, 0.84 kept
- DoD-4 no embedding server -> row created with embedding None, no embed call
- DoD-5 first memory in empty session is never a duplicate
- DoD-6 lazy backfill: an existing embedding-less row is embedded and compared

Mirrors the mocking style of `tests/services/test_memory_dedup.py`: monkeypatch
`memory_compaction.is_embedding_configured` / `memory_compaction.embed_texts`
with hand-crafted vectors of known cosine, and read rows back via the db layer.
Expected values come from the plan spec, not from any implementation.
"""

import math

import pytest

from app.db import chats as chats_db
from app.models.chat_memory import ChatMemory
from app.services import chat_tools
from app.services import memory_compaction
from app.services.memory_compaction import (
    MEMORY_DEDUP_INLINE_COSINE_THRESHOLD,
    find_duplicate_memory,
)
from app.services.snowflake import generate_id

from datetime import datetime, timezone


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

    Returns a list capturing each batch of texts passed to embed_texts so tests
    can assert on call shape (e.g. that no embed call happens when unconfigured).
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


def _unit_with_cosine(c: float) -> list[float]:
    """Unit vector whose cosine to [1.0, 0.0] is exactly `c`."""
    return [c, math.sqrt(1.0 - c * c)]


# ---------------------------------------------------------------------------
# DoD-1 — near-duplicate is suppressed
# ---------------------------------------------------------------------------


async def test_inline_dedup_suppresses_near_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DoD-1: candidate with cosine >= 0.85 to an existing memory is NOT
    persisted; add_memory_impl still returns 'Memory saved.' and appends no id."""
    session_id = generate_id()
    existing_content = "User trusts the blacksmith."
    candidate_content = "The user trusts the smith."

    existing_id = await _create_memory(
        session_id, existing_content, embedding=[1.0, 0.0]
    )

    vectors = {
        existing_content: [1.0, 0.0],
        candidate_content: _unit_with_cosine(0.95),  # cosine 0.95 >= 0.85 -> drop
    }
    _patch_embedding(monkeypatch, configured=True, vectors=vectors)

    saved_ids: list[int] = []
    result = await chat_tools.add_memory_impl(
        session_id, candidate_content, saved_memory_ids=saved_ids
    )

    assert result == "Memory saved."
    assert saved_ids == []  # nothing appended for a suppressed duplicate

    remaining = await chats_db.list_memories(session_id)
    assert [m.id for m in remaining] == [existing_id]  # row count unchanged


# ---------------------------------------------------------------------------
# DoD-2 — distinct candidate is kept and its embedding stored
# ---------------------------------------------------------------------------


async def test_inline_dedup_keeps_distinct_and_stores_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DoD-2: candidate with cosine < 0.85 to every existing memory is persisted
    with its computed embedding; its new id is appended to saved_memory_ids."""
    session_id = generate_id()
    existing_content = "User fears the forest."
    candidate_content = "User enjoys cooking stew."

    existing_id = await _create_memory(
        session_id, existing_content, embedding=[1.0, 0.0]
    )

    candidate_vec = _unit_with_cosine(0.5)  # cosine 0.5 < 0.85 -> keep
    vectors = {
        existing_content: [1.0, 0.0],
        candidate_content: candidate_vec,
    }
    _patch_embedding(monkeypatch, configured=True, vectors=vectors)

    saved_ids: list[int] = []
    result = await chat_tools.add_memory_impl(
        session_id, candidate_content, saved_memory_ids=saved_ids
    )

    assert result == "Memory saved."

    rows = await chats_db.list_memories(session_id)
    new_rows = [m for m in rows if m.id != existing_id]
    assert len(new_rows) == 1
    new_row = new_rows[0]
    assert new_row.content == candidate_content
    assert new_row.embedding == candidate_vec  # candidate's vector persisted
    assert saved_ids == [new_row.id]  # new id collected


# ---------------------------------------------------------------------------
# DoD-3 — threshold is inclusive (>=)
# ---------------------------------------------------------------------------


async def test_inline_dedup_threshold_inclusive_at_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DoD-3a: a candidate at cosine exactly the threshold is a duplicate
    (comparison is >= MEMORY_DEDUP_INLINE_COSINE_THRESHOLD)."""
    session_id = generate_id()
    existing_content = "Boundary peer."
    candidate_content = "Boundary candidate at threshold."

    existing_id = await _create_memory(
        session_id, existing_content, embedding=[1.0, 0.0]
    )

    # Cosine of [1,0] and [T, sqrt(1-T^2)] is exactly T.
    at_threshold = _unit_with_cosine(MEMORY_DEDUP_INLINE_COSINE_THRESHOLD)
    vectors = {candidate_content: at_threshold}
    _patch_embedding(monkeypatch, configured=True, vectors=vectors)

    result = await find_duplicate_memory(session_id, candidate_content)

    assert result.is_duplicate is True
    assert result.duplicate_of_id == existing_id
    assert result.similarity is not None
    assert result.similarity >= MEMORY_DEDUP_INLINE_COSINE_THRESHOLD


async def test_inline_dedup_threshold_inclusive_below_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DoD-3b: a candidate just below the threshold (0.84) is kept (not a
    duplicate)."""
    session_id = generate_id()
    existing_content = "Below-boundary peer."
    candidate_content = "Below-boundary candidate."

    await _create_memory(session_id, existing_content, embedding=[1.0, 0.0])

    below = MEMORY_DEDUP_INLINE_COSINE_THRESHOLD - 0.01  # 0.84 < 0.85 -> keep
    vectors = {candidate_content: _unit_with_cosine(below)}
    _patch_embedding(monkeypatch, configured=True, vectors=vectors)

    result = await find_duplicate_memory(session_id, candidate_content)

    assert result.is_duplicate is False


# ---------------------------------------------------------------------------
# DoD-4 — no embedding server
# ---------------------------------------------------------------------------


async def test_inline_dedup_no_embedding_server_inserts_without_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DoD-4: with is_embedding_configured() False the row is created with
    embedding None, no candidate embed call is made, and the return is
    'Memory saved.' with no exception raised."""
    session_id = generate_id()
    candidate_content = "Saved without an embedding server."

    # vectors=None -> embed_texts raises AssertionError if it is ever called.
    calls = _patch_embedding(monkeypatch, configured=False, vectors=None)

    saved_ids: list[int] = []
    result = await chat_tools.add_memory_impl(
        session_id, candidate_content, saved_memory_ids=saved_ids
    )

    assert result == "Memory saved."
    assert calls == []  # no embed round-trip when unconfigured

    rows = await chats_db.list_memories(session_id)
    assert len(rows) == 1
    assert rows[0].content == candidate_content
    assert rows[0].embedding is None
    assert saved_ids == [rows[0].id]


# ---------------------------------------------------------------------------
# DoD-5 — first memory in an empty session
# ---------------------------------------------------------------------------


async def test_inline_dedup_first_memory_empty_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DoD-5: with an empty comparison set the candidate is never a duplicate;
    the row is created carrying its computed embedding."""
    session_id = generate_id()
    candidate_content = "The very first memory."
    candidate_vec = [0.3, 0.4, 0.5]

    vectors = {candidate_content: candidate_vec}
    _patch_embedding(monkeypatch, configured=True, vectors=vectors)

    # No peers -> not a duplicate, but the candidate embedding is computed.
    check = await find_duplicate_memory(session_id, candidate_content)
    assert check.is_duplicate is False
    assert check.embedding == candidate_vec

    saved_ids: list[int] = []
    result = await chat_tools.add_memory_impl(
        session_id, candidate_content, saved_memory_ids=saved_ids
    )

    assert result == "Memory saved."
    rows = await chats_db.list_memories(session_id)
    assert len(rows) == 1
    assert rows[0].content == candidate_content
    assert rows[0].embedding == candidate_vec
    assert saved_ids == [rows[0].id]


# ---------------------------------------------------------------------------
# DoD-6 — lazy backfill of an embedding-less existing row
# ---------------------------------------------------------------------------


async def test_inline_dedup_lazy_backfill_existing_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DoD-6: an existing row whose embedding is None is embedded and persisted
    during find_duplicate_memory and participates in the comparison."""
    session_id = generate_id()
    existing_content = "User collects old maps."
    candidate_content = "The user collects ancient maps."

    # Existing row stored WITHOUT an embedding -> must be backfilled.
    existing_id = await _create_memory(session_id, existing_content, embedding=None)

    existing_vec = [1.0, 0.0]
    candidate_vec = _unit_with_cosine(0.99)  # cosine 0.99 >= 0.85 -> duplicate
    vectors = {
        existing_content: existing_vec,
        candidate_content: candidate_vec,
    }
    calls = _patch_embedding(monkeypatch, configured=True, vectors=vectors)

    result = await find_duplicate_memory(session_id, candidate_content)

    # Single batched embed round-trip covering candidate + backfilled peer.
    assert len(calls) == 1
    assert set(calls[0]) == {existing_content, candidate_content}

    # The embedding-less peer participated and was the matched duplicate.
    assert result.is_duplicate is True
    assert result.duplicate_of_id == existing_id
    assert result.similarity is not None
    assert result.similarity >= MEMORY_DEDUP_INLINE_COSINE_THRESHOLD

    # Backfill persisted: read the existing row back, its embedding is now stored.
    rows = await chats_db.list_memories(session_id)
    backfilled = next(m for m in rows if m.id == existing_id)
    assert backfilled.embedding == existing_vec
