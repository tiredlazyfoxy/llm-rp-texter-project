"""World data access. Session-free public API — all sessions managed internally."""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.world import (
    NPCLocationLink,
    World,
    WorldLocation,
    WorldLoreFact,
    WorldNPC,
    WorldRule,
    WorldStatDefinition,
)


# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------


async def get_world_by_id(world_id: int) -> World | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(World).where(World.id == world_id))).one_or_none()


async def list_worlds() -> list[World]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(select(World))).all())


async def create_world(world: World) -> World:
    session = await get_standalone_session()
    async with session:
        session.add(world)
        await session.commit()
        await session.refresh(world)
        return world


async def update_world(world: World) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(world)
        await session.commit()


async def delete_world(world_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        world = (await session.exec(select(World).where(World.id == world_id))).one_or_none()
        if world is None:
            return False
        await session.delete(world)
        await session.commit()
        return True


# ---------------------------------------------------------------------------
# World Locations
# ---------------------------------------------------------------------------


async def get_location_by_id(location_id: int) -> WorldLocation | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(WorldLocation).where(WorldLocation.id == location_id))).one_or_none()


async def list_locations_by_world(world_id: int) -> list[WorldLocation]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(select(WorldLocation).where(WorldLocation.world_id == world_id))).all())


async def create_location(location: WorldLocation) -> WorldLocation:
    session = await get_standalone_session()
    async with session:
        session.add(location)
        await session.commit()
        await session.refresh(location)
        return location


async def update_location(location: WorldLocation) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(location)
        await session.commit()


async def delete_location(location_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        loc = (await session.exec(select(WorldLocation).where(WorldLocation.id == location_id))).one_or_none()
        if loc is None:
            return False
        await session.delete(loc)
        await session.commit()
        return True


# ---------------------------------------------------------------------------
# World NPCs
# ---------------------------------------------------------------------------


async def get_npc_by_id(npc_id: int) -> WorldNPC | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(WorldNPC).where(WorldNPC.id == npc_id))).one_or_none()


async def list_npcs_by_world(world_id: int) -> list[WorldNPC]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(select(WorldNPC).where(WorldNPC.world_id == world_id))).all())


async def create_npc(npc: WorldNPC) -> WorldNPC:
    session = await get_standalone_session()
    async with session:
        session.add(npc)
        await session.commit()
        await session.refresh(npc)
        return npc


async def update_npc(npc: WorldNPC) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(npc)
        await session.commit()


async def delete_npc(npc_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        npc = (await session.exec(select(WorldNPC).where(WorldNPC.id == npc_id))).one_or_none()
        if npc is None:
            return False
        await session.delete(npc)
        await session.commit()
        return True


# ---------------------------------------------------------------------------
# World Lore Facts
# ---------------------------------------------------------------------------


async def get_lore_fact_by_id(fact_id: int) -> WorldLoreFact | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(WorldLoreFact).where(WorldLoreFact.id == fact_id))).one_or_none()


async def list_lore_facts_by_world(world_id: int) -> list[WorldLoreFact]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(select(WorldLoreFact).where(WorldLoreFact.world_id == world_id))).all())


async def create_lore_fact(fact: WorldLoreFact) -> WorldLoreFact:
    session = await get_standalone_session()
    async with session:
        session.add(fact)
        await session.commit()
        await session.refresh(fact)
        return fact


async def update_lore_fact(fact: WorldLoreFact) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(fact)
        await session.commit()


async def delete_lore_fact(fact_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        fact = (await session.exec(select(WorldLoreFact).where(WorldLoreFact.id == fact_id))).one_or_none()
        if fact is None:
            return False
        await session.delete(fact)
        await session.commit()
        return True


# ---------------------------------------------------------------------------
# NPC Location Links
# ---------------------------------------------------------------------------


async def get_npc_link_by_id(link_id: int) -> NPCLocationLink | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(NPCLocationLink).where(NPCLocationLink.id == link_id))).one_or_none()


async def list_npc_links_by_npc(npc_id: int) -> list[NPCLocationLink]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(select(NPCLocationLink).where(NPCLocationLink.npc_id == npc_id))).all())


async def list_npc_links_by_location(location_id: int) -> list[NPCLocationLink]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(
            select(NPCLocationLink).where(NPCLocationLink.location_id == location_id)
        )).all())


async def create_npc_link(link: NPCLocationLink) -> NPCLocationLink:
    session = await get_standalone_session()
    async with session:
        session.add(link)
        await session.commit()
        await session.refresh(link)
        return link


async def delete_npc_link(link_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        link = (await session.exec(select(NPCLocationLink).where(NPCLocationLink.id == link_id))).one_or_none()
        if link is None:
            return False
        await session.delete(link)
        await session.commit()
        return True


# ---------------------------------------------------------------------------
# World Stat Definitions
# ---------------------------------------------------------------------------


async def get_stat_definition_by_id(stat_id: int) -> WorldStatDefinition | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(WorldStatDefinition).where(WorldStatDefinition.id == stat_id))).one_or_none()


async def list_stat_definitions_by_world(world_id: int) -> list[WorldStatDefinition]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(
            select(WorldStatDefinition).where(WorldStatDefinition.world_id == world_id)
        )).all())


async def create_stat_definition(stat: WorldStatDefinition) -> WorldStatDefinition:
    session = await get_standalone_session()
    async with session:
        session.add(stat)
        await session.commit()
        await session.refresh(stat)
        return stat


async def update_stat_definition(stat: WorldStatDefinition) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(stat)
        await session.commit()


async def delete_stat_definition(stat_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        stat = (await session.exec(
            select(WorldStatDefinition).where(WorldStatDefinition.id == stat_id)
        )).one_or_none()
        if stat is None:
            return False
        await session.delete(stat)
        await session.commit()
        return True


# ---------------------------------------------------------------------------
# World Rules
# ---------------------------------------------------------------------------


async def get_rule_by_id(rule_id: int) -> WorldRule | None:
    session = await get_standalone_session()
    async with session:
        return (await session.exec(select(WorldRule).where(WorldRule.id == rule_id))).one_or_none()


async def list_rules_by_world(world_id: int) -> list[WorldRule]:
    session = await get_standalone_session()
    async with session:
        return list((await session.exec(
            select(WorldRule).where(WorldRule.world_id == world_id).order_by(WorldRule.order)
        )).all())


async def create_rule(rule: WorldRule) -> WorldRule:
    session = await get_standalone_session()
    async with session:
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule


async def update_rule(rule: WorldRule) -> None:
    session = await get_standalone_session()
    async with session:
        await session.merge(rule)
        await session.commit()


async def delete_rule(rule_id: int) -> bool:
    session = await get_standalone_session()
    async with session:
        rule = (await session.exec(select(WorldRule).where(WorldRule.id == rule_id))).one_or_none()
        if rule is None:
            return False
        await session.delete(rule)
        await session.commit()
        return True
