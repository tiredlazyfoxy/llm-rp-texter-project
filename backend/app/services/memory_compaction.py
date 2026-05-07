"""Memory compaction — between Phase 1 and Phase 2 of summarization.

Embeds the newly-created `ChatMemory` rows from Phase 1, cosine-compares each
against every other memory in the session (lazily backfilling embeddings on
pre-existing rows that lack them), drops new rows whose similarity to any peer
meets `MEMORY_DEDUP_COSINE_THRESHOLD`, and persists the surviving embeddings.

Pure helper — no SSE plumbing here. The caller (`summarization_service`) reads
the returned `MemoryCompactionResult` and emits the `memory_compaction` event.
"""

from __future__ import annotations

import logging
import math

from pydantic import BaseModel

from app.db import chats as chats_db
from app.services.embedding import (
    EmbeddingNotConfiguredError,
    embed_texts,
    is_embedding_configured,
)

logger = logging.getLogger(__name__)


MEMORY_DEDUP_COSINE_THRESHOLD: float = 0.92


class MemoryRef(BaseModel):
    id: int
    content: str


class DroppedMemory(BaseModel):
    id: int
    content: str
    duplicate_of_id: int
    duplicate_of_content: str
    similarity: float


class MemoryCompactionResult(BaseModel):
    kept: list[MemoryRef]
    dropped: list[DroppedMemory]
    skipped: bool = False
    skip_reason: str | None = None


def _cosine(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity. Returns 0.0 when either vector is
    zero-length or zero-norm."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


async def compact_new_memories(
    session_id: int,
    new_memory_ids: list[int],
) -> MemoryCompactionResult:
    """Embed the new rows, compare against every other session memory via
    cosine, delete the new ones above threshold, persist embeddings on the
    kept rows. Returns kept/dropped lists. Returns `skipped=True` (and writes
    nothing) when no embedding server is configured or when `new_memory_ids`
    is empty.
    """
    if not new_memory_ids:
        return MemoryCompactionResult(
            kept=[], dropped=[], skipped=True, skip_reason="no_new_memories",
        )

    if not await is_embedding_configured():
        logger.debug("Memory compaction skipped: no embedding server configured")
        return MemoryCompactionResult(
            kept=[], dropped=[], skipped=True, skip_reason="no_embedding_server",
        )

    new_ids_set = set(new_memory_ids)
    all_memories = await chats_db.list_memories(session_id)

    # Index everything for fast lookup; preserve "new vs existing" classification.
    by_id = {m.id: m for m in all_memories}
    new_rows = [by_id[mid] for mid in new_memory_ids if mid in by_id]
    existing_rows = [m for m in all_memories if m.id not in new_ids_set]

    if not new_rows:
        # The IDs we were given don't exist anymore (deleted concurrently?).
        return MemoryCompactionResult(
            kept=[], dropped=[], skipped=True, skip_reason="no_new_memories",
        )

    # Targets that need embedding: every new row (always, since add_memory
    # writes without embedding) plus every pre-existing row that lacks one
    # (lazy backfill so the comparison set is complete and the row is cheap
    # to compare next time).
    needs_embedding: list[tuple[int, str]] = []
    for row in new_rows:
        if row.embedding is None:
            needs_embedding.append((row.id, row.content))
    for row in existing_rows:
        if row.embedding is None:
            needs_embedding.append((row.id, row.content))

    fresh_embeddings: dict[int, list[float]] = {}
    if needs_embedding:
        try:
            vectors = await embed_texts([text for _, text in needs_embedding])
        except EmbeddingNotConfiguredError:
            logger.debug("Memory compaction skipped mid-flight: embedding not configured")
            return MemoryCompactionResult(
                kept=[], dropped=[], skipped=True, skip_reason="no_embedding_server",
            )
        for (mid, _content), vec in zip(needs_embedding, vectors):
            fresh_embeddings[mid] = vec

    def _vec_for(mid: int) -> list[float] | None:
        if mid in fresh_embeddings:
            return fresh_embeddings[mid]
        row = by_id.get(mid)
        return row.embedding if row is not None else None

    # Walk new rows in id-ascending (creation-time) order so the older new
    # row wins ties against later new rows in the same run. Each new row is
    # compared against (a) every pre-existing row and (b) earlier new rows
    # that have already survived this pass — never against later new rows
    # that haven't been processed yet, since the younger one must lose.
    sorted_new = sorted(new_rows, key=lambda r: r.id)
    dropped: list[DroppedMemory] = []
    dropped_ids: set[int] = set()
    kept_new: list[int] = []
    survivor_new_ids: list[int] = []  # earlier-this-run new rows that survived

    for row in sorted_new:
        my_vec = _vec_for(row.id)
        if my_vec is None:
            kept_new.append(row.id)
            survivor_new_ids.append(row.id)
            continue

        peer_ids: list[int] = [m.id for m in existing_rows]
        peer_ids.extend(survivor_new_ids)

        best_id: int | None = None
        best_sim: float = -1.0
        for peer_id in peer_ids:
            peer_vec = _vec_for(peer_id)
            if peer_vec is None:
                continue
            sim = _cosine(my_vec, peer_vec)
            if sim > best_sim:
                best_sim = sim
                best_id = peer_id

        if best_id is not None and best_sim >= MEMORY_DEDUP_COSINE_THRESHOLD:
            peer = by_id[best_id]
            dropped.append(DroppedMemory(
                id=row.id,
                content=row.content,
                duplicate_of_id=peer.id,
                duplicate_of_content=peer.content,
                similarity=best_sim,
            ))
            dropped_ids.add(row.id)
        else:
            kept_new.append(row.id)
            survivor_new_ids.append(row.id)

    # Persist surviving embeddings. Fresh embeddings for dropped rows would
    # be wasted writes — exclude them.
    persist: dict[int, list[float]] = {
        mid: vec for mid, vec in fresh_embeddings.items() if mid not in dropped_ids
    }
    if persist:
        await chats_db.update_memory_embeddings(persist)

    if dropped_ids:
        await chats_db.delete_memories(list(dropped_ids))

    kept_refs = [
        MemoryRef(id=mid, content=by_id[mid].content)
        for mid in kept_new
        if mid in by_id
    ]

    return MemoryCompactionResult(
        kept=kept_refs,
        dropped=dropped,
        skipped=False,
        skip_reason=None,
    )
