"""World data access. Session-free public API — all sessions managed internally."""

from sqlalchemy import or_
from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.world import World, WorldLocation, WorldLoreFact, WorldNPC, WorldStatus


# ---------------------------------------------------------------------------
# Initial-message placeholder normalization
# ---------------------------------------------------------------------------
#
# Single source of truth for the lowercase → uppercase token rewrite applied
# during the one-time data migration (`normalize_initial_message_placeholders`)
# and at JSONL import time (via `rewrite_initial_message_tokens`).
#
# The chat service performs runtime *value* substitution on the uppercase
# tokens directly and deliberately does not import this helper — the two
# concerns (token-shape rewrite vs runtime value substitution) have different
# lifetimes and must not be coupled.

INITIAL_MESSAGE_TOKEN_REWRITES: tuple[tuple[str, str], ...] = (
    ("{character_name}", "{CHARACTER_NAME}"),
    ("{location_name}", "{LOCATION_NAME}"),
    ("{location_summary}", "{LOCATION_SUMMARY}"),
)


def rewrite_initial_message_tokens(text: str) -> str:
    """Apply INITIAL_MESSAGE_TOKEN_REWRITES; idempotent."""
    if not text:
        return text
    for old, new in INITIAL_MESSAGE_TOKEN_REWRITES:
        text = text.replace(old, new)
    return text


async def get_by_id(world_id: int) -> World | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(World).where(World.id == world_id))).one_or_none()


async def list_all() -> list[World]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(select(World))).all())


async def list_for_user(user_id: int) -> list[World]:
    """List worlds visible to a non-admin user: excludes others' private worlds."""
    session = await get_standalone_session()
    async with session:
        q = select(World).where(
            or_(
                World.status != WorldStatus.private,  # type: ignore[arg-type]
                World.owner_id == user_id,  # type: ignore[arg-type]
                World.owner_id.is_(None),  # type: ignore[union-attr]
            )
        )
        return list((await session.exec(q)).all())


async def create(world: World) -> World:
    session = await get_standalone_session()
    async with session:
        session.add(world)
        await session.commit()
        await session.refresh(world)
        return world


async def update(world: World) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(world)
        await session.commit()


async def delete(world_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        world = (await session.exec(select(World).where(World.id == world_id))).one_or_none()
        if world is None:
            return False
        await session.delete(world)
        await session.commit()
        return True


async def normalize_initial_message_placeholders() -> int:
    """
    Rewrite lowercase placeholder tokens in every World.initial_message
    to their uppercase form. Idempotent. Returns the number of rows
    actually changed.
    """
    session = await get_standalone_session()
    async with session:
        worlds = list((await session.exec(select(World))).all())
        changed = 0
        for w in worlds:
            original = w.initial_message or ""
            rewritten = rewrite_initial_message_tokens(original)
            if rewritten != original:
                w.initial_message = rewritten
                session.add(w)
                changed += 1
        if changed:
            await session.commit()
        return changed


async def document_id_exists(doc_id: int) -> bool:
    """Check if a snowflake id is already used by any document table
    (`WorldLocation`, `WorldNPC`, `WorldLoreFact`). The three tables share
    a single id space conceptually."""
    session = await get_standalone_session()
    async with session:
        loc = (await session.exec(
            select(WorldLocation.id).where(WorldLocation.id == doc_id)
        )).one_or_none()
        if loc is not None:
            return True
        npc = (await session.exec(
            select(WorldNPC.id).where(WorldNPC.id == doc_id)
        )).one_or_none()
        if npc is not None:
            return True
        fact = (await session.exec(
            select(WorldLoreFact.id).where(WorldLoreFact.id == doc_id)
        )).one_or_none()
        return fact is not None
