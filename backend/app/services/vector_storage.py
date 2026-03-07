"""LanceDB vector storage for world knowledge documents.

Chunks documents, embeds them, and provides semantic search scoped per world.
Embedding model is a placeholder — to be replaced with a configurable model.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

import lancedb
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.world import WorldLocation, WorldLoreFact, WorldNPC

logger = logging.getLogger(__name__)

VECTOR_DIM = 384
_VECTOR_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "vector"
_TABLE_NAME = "chunks"

_db: Any = None


class VectorChunk(BaseModel):
    id: str
    world_id: int
    source_type: str  # "location" | "npc" | "lore_fact"
    source_id: int
    chunk_index: int
    text: str
    vector: list[float]


# ---------------------------------------------------------------------------
# Text chunking (placeholder — paragraph-based)
# ---------------------------------------------------------------------------

def _chunk_text(text: str, max_chunk_size: int = 500) -> list[str]:
    """Split text into chunks by paragraphs, merging small ones."""
    if not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if current and len(current) + len(para) + 2 > max_chunk_size:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para

    if current:
        chunks.append(current)

    return chunks


# ---------------------------------------------------------------------------
# Embedding (placeholder — hash-based deterministic vectors)
# TODO: replace with configurable embedding model
# ---------------------------------------------------------------------------

def _embed(texts: list[str]) -> list[list[float]]:
    """Generate placeholder embeddings. Deterministic hash-based vectors."""
    import hashlib

    vectors = []
    for text in texts:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        # Repeat hash bytes to fill VECTOR_DIM floats, normalize to [-1, 1]
        raw = []
        for i in range(VECTOR_DIM):
            byte_val = h[i % len(h)]
            raw.append((byte_val / 127.5) - 1.0)
        # Simple normalization
        norm = max(sum(v * v for v in raw) ** 0.5, 1e-9)
        vectors.append([v / norm for v in raw])
    return vectors


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def init_vector_store() -> None:
    """Initialize LanceDB connection."""
    global _db
    _VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    _db = await asyncio.to_thread(lancedb.connect, str(_VECTOR_DIR))
    logger.info("Vector store initialized at %s", _VECTOR_DIR)


def _get_table() -> Any | None:
    """Get the chunks table, or None if it doesn't exist yet."""
    if _db is None:
        return None
    try:
        return _db.open_table(_TABLE_NAME)
    except Exception:
        return None


def _ensure_table() -> Any:
    """Get or create the chunks table."""
    if _db is None:
        raise RuntimeError("Vector store not initialized")

    table = _get_table()
    if table is not None:
        return table

    import pyarrow as pa

    schema = pa.schema([
        pa.field("id", pa.string()),
        pa.field("world_id", pa.int64()),
        pa.field("source_type", pa.string()),
        pa.field("source_id", pa.int64()),
        pa.field("chunk_index", pa.int32()),
        pa.field("text", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), VECTOR_DIM)),
    ])
    return _db.create_table(_TABLE_NAME, schema=schema)


async def index_document(
    world_id: int, source_type: str, source_id: int, text: str
) -> None:
    """Chunk text, embed, delete old chunks for this source, insert new."""

    def _do() -> None:
        table = _ensure_table()

        # Delete old chunks for this source
        try:
            table.delete(f"source_type = '{source_type}' AND source_id = {source_id}")
        except Exception:
            pass  # Table may be empty

        chunks = _chunk_text(text)
        if not chunks:
            return

        vectors = _embed(chunks)
        rows = [
            {
                "id": f"{source_type}_{source_id}_{i}",
                "world_id": world_id,
                "source_type": source_type,
                "source_id": source_id,
                "chunk_index": i,
                "text": chunk,
                "vector": vec,
            }
            for i, (chunk, vec) in enumerate(zip(chunks, vectors))
        ]
        table.add(rows)

    await asyncio.to_thread(_do)
    logger.debug(
        "Indexed document %s/%d for world %d", source_type, source_id, world_id
    )


async def delete_document(source_type: str, source_id: int) -> None:
    """Delete all chunks for a given source document."""

    def _do() -> None:
        table = _get_table()
        if table is None:
            return
        try:
            table.delete(f"source_type = '{source_type}' AND source_id = {source_id}")
        except Exception:
            pass

    await asyncio.to_thread(_do)


async def delete_world_index(world_id: int) -> None:
    """Delete all chunks for an entire world."""

    def _do() -> None:
        table = _get_table()
        if table is None:
            return
        try:
            table.delete(f"world_id = {world_id}")
        except Exception:
            pass

    await asyncio.to_thread(_do)


async def search(
    world_id: int,
    query: str,
    source_type: str | None = None,
    limit: int = 5,
) -> list[VectorChunk]:
    """Vector search filtered by world_id and optionally source_type."""

    def _do() -> list[VectorChunk]:
        table = _get_table()
        if table is None:
            return []

        query_vec = _embed([query])[0]
        where = f"world_id = {world_id}"
        if source_type:
            where += f" AND source_type = '{source_type}'"

        try:
            results = (
                table.search(query_vec)
                .where(where)
                .limit(limit)
                .to_list()
            )
        except Exception:
            return []

        return [
            VectorChunk(
                id=r["id"],
                world_id=r["world_id"],
                source_type=r["source_type"],
                source_id=r["source_id"],
                chunk_index=r["chunk_index"],
                text=r["text"],
                vector=r["vector"],
            )
            for r in results
        ]

    return await asyncio.to_thread(_do)


async def rebuild_all_worlds_index(session: AsyncSession) -> None:
    """Rebuild vector indices for all worlds from DB documents.

    Called after database import to reconstruct the vector store.
    """
    # Drop and recreate table
    def _reset_table() -> None:
        if _db is None:
            return
        try:
            _db.drop_table(_TABLE_NAME)
        except Exception:
            pass

    await asyncio.to_thread(_reset_table)

    # Index all locations
    result = await session.execute(select(WorldLocation))
    for loc in result.scalars().all():
        await index_document(loc.world_id, "location", loc.id, loc.content)

    # Index all NPCs
    result = await session.execute(select(WorldNPC))
    for npc in result.scalars().all():
        await index_document(npc.world_id, "npc", npc.id, npc.content)

    # Index all lore facts
    result = await session.execute(select(WorldLoreFact))
    for fact in result.scalars().all():
        await index_document(fact.world_id, "lore_fact", fact.id, fact.content)

    logger.info("Vector index rebuilt for all worlds")
