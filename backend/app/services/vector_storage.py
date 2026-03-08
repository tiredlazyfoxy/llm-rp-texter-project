"""LanceDB vector storage for world knowledge documents.

Chunks documents, embeds them via the configured embedding server,
and provides semantic search scoped per world.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

import lancedb
from pydantic import BaseModel

from app.services.embedding import EmbeddingNotConfiguredError

logger = logging.getLogger(__name__)

_DEFAULT_VECTOR_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "vector"
_TABLE_NAME = "chunks"

_vector_dir: Path = _DEFAULT_VECTOR_DIR
_db: Any = None
# Dynamic vector dimension — set on first embedding call
_vector_dim: int | None = None


class VectorChunk(BaseModel):
    id: str
    world_id: int
    source_type: str  # "location" | "npc" | "lore_fact"
    source_id: int
    chunk_index: int
    text: str
    vector: list[float]


class IndexResult(BaseModel):
    """Result of an indexing operation."""
    indexed: bool
    warning: str | None = None


# ---------------------------------------------------------------------------
# Text chunking (paragraph-based)
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
# Public interface
# ---------------------------------------------------------------------------

async def init_vector_store(vector_dir: Path | None = None) -> None:
    """Initialize LanceDB connection. Accepts optional path override for tests."""
    global _db, _vector_dir
    if vector_dir is not None:
        _vector_dir = vector_dir
    _vector_dir.mkdir(parents=True, exist_ok=True)
    _db = await asyncio.to_thread(lancedb.connect, str(_vector_dir))
    logger.info("Vector store initialized at %s", _vector_dir)


def _get_table() -> Any | None:
    """Get the chunks table, or None if it doesn't exist yet."""
    if _db is None:
        return None
    try:
        return _db.open_table(_TABLE_NAME)
    except Exception:
        return None


def _ensure_table(dim: int) -> Any:
    """Get or create the chunks table with the given vector dimension."""
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
        pa.field("vector", pa.list_(pa.float32(), dim)),
    ])
    return _db.create_table(_TABLE_NAME, schema=schema)


async def index_document(
    world_id: int, source_type: str, source_id: int, text: str
) -> IndexResult:
    """Chunk text, embed via configured server, update LanceDB.

    Returns IndexResult with indexed=False and a warning if embedding is not configured.
    """
    from app.services import embedding

    global _vector_dim

    chunks = _chunk_text(text)

    # Delete old chunks regardless of whether we can embed new ones
    def _delete_old() -> None:
        table = _get_table()
        if table is None:
            return
        try:
            table.delete(f"source_type = '{source_type}' AND source_id = {source_id}")
        except Exception:
            pass

    await asyncio.to_thread(_delete_old)

    if not chunks:
        return IndexResult(indexed=True)

    # Embed chunks
    try:
        vectors = await embedding.embed_texts(chunks)
    except EmbeddingNotConfiguredError as e:
        logger.debug("Skipping indexing for %s/%d: %s", source_type, source_id, e)
        return IndexResult(indexed=False, warning=str(e))

    # Detect / cache dimension
    if _vector_dim is None and vectors:
        _vector_dim = len(vectors[0])

    dim = _vector_dim
    assert dim is not None

    # Insert into LanceDB (blocking I/O)
    def _insert() -> None:
        table = _ensure_table(dim)
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

    await asyncio.to_thread(_insert)
    logger.debug(
        "Indexed document %s/%d for world %d", source_type, source_id, world_id
    )
    return IndexResult(indexed=True)


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
    """Vector search filtered by world_id and optionally source_type.

    Returns empty list if embedding is not configured.
    """
    from app.services import embedding

    try:
        query_vec = (await embedding.embed_texts([query]))[0]
    except EmbeddingNotConfiguredError:
        logger.debug("Search skipped — no embedding server configured")
        return []

    def _do() -> list[VectorChunk]:
        table = _get_table()
        if table is None:
            return []

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


async def rebuild_all_worlds_index() -> int:
    """Rebuild vector indices for all worlds from DB documents.

    Called after database import or when admin triggers manual reindex.
    Returns the number of documents indexed.

    Raises EmbeddingNotConfiguredError if no embedding server is set.
    """
    from app.db import locations, lore_facts, npcs, worlds
    from app.services import embedding

    # Verify embedding is available before starting
    if not await embedding.is_embedding_configured():
        raise EmbeddingNotConfiguredError("Cannot reindex: no embedding server configured")

    global _vector_dim
    _vector_dim = None  # Reset so dimension is re-detected

    # Drop and recreate table
    def _reset_table() -> None:
        if _db is None:
            return
        try:
            _db.drop_table(_TABLE_NAME)
        except Exception:
            pass

    await asyncio.to_thread(_reset_table)

    doc_count = 0
    all_worlds = await worlds.list_all()
    for world in all_worlds:
        for loc in await locations.list_by_world(world.id):  # type: ignore[arg-type]
            await index_document(world.id, "location", loc.id, loc.content)  # type: ignore[arg-type]
            doc_count += 1

        for npc in await npcs.list_by_world(world.id):  # type: ignore[arg-type]
            await index_document(world.id, "npc", npc.id, npc.content)  # type: ignore[arg-type]
            doc_count += 1

        for fact in await lore_facts.list_by_world(world.id):  # type: ignore[arg-type]
            await index_document(world.id, "lore_fact", fact.id, fact.content)  # type: ignore[arg-type]
            doc_count += 1

    logger.info("Vector index rebuilt for all worlds (%d documents)", doc_count)
    return doc_count
