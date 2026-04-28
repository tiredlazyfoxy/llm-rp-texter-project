"""World editor — business logic for worlds, documents, stats, rules, and links."""

import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from typing import TypedDict

from fastapi import HTTPException, status

from app.db import locations, lore_facts, npc_links, npcs, rules, stat_defs, worlds
from app.models.schemas.worlds import (
    CreateDocumentRequest,
    CreateNpcLocationLinkRequest,
    CreateRuleRequest,
    CreateStatRequest,
    CreateWorldRequest,
    UpdateDocumentRequest,
    UpdateRuleRequest,
    UpdateStatRequest,
    UpdateWorldRequest,
)
from app.models.world import (
    NPCLocationLink,
    NPCLinkType,
    StatScope,
    StatType,
    World,
    WorldLocation,
    WorldLoreFact,
    WorldNPC,
    WorldRule,
    WorldStatDefinition,
    WorldStatus,
)
from app.services import vector_storage
from app.services.snowflake import generate_id

logger = logging.getLogger(__name__)

_VALID_DOC_TYPES = {"location", "npc", "lore_fact"}
_VALID_STATUSES = {s.value for s in WorldStatus}
_VALID_SCOPES = {s.value for s in StatScope}
_VALID_STAT_TYPES = {s.value for s in StatType}
_VALID_LINK_TYPES = {t.value for t in NPCLinkType}
_VALID_GENERATION_MODES = {"simple", "chain", "agentic"}

# Map doc_type to vector storage source_type (they happen to be the same)
_DOC_SOURCE_TYPE = {"location": "location", "npc": "npc", "lore_fact": "lore_fact"}


# ── TypedDicts for internal data passing ──────────────────────────

class DocumentData(TypedDict):
    doc_type: str
    obj: WorldLocation | WorldNPC | WorldLoreFact


class IndexResultInfo(TypedDict):
    embedding_warning: str | None


# ── Helpers ───────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_doc_type(doc_type: str) -> None:
    if doc_type not in _VALID_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid doc_type: {doc_type}. Must be one of: {', '.join(sorted(_VALID_DOC_TYPES))}",
        )


def _validate_status(s: str) -> None:
    if s not in _VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {s}. Must be one of: {', '.join(sorted(_VALID_STATUSES))}",
        )


async def _require_world(world_id: int) -> World:
    world = await worlds.get_by_id(world_id)
    if world is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    return world


async def _find_document(doc_id: int) -> DocumentData:
    """Try all three tables to find a document by Snowflake ID."""
    loc = await locations.get_by_id(doc_id)
    if loc is not None:
        return DocumentData(doc_type="location", obj=loc)

    npc = await npcs.get_by_id(doc_id)
    if npc is not None:
        return DocumentData(doc_type="npc", obj=npc)

    fact = await lore_facts.get_by_id(doc_id)
    if fact is not None:
        return DocumentData(doc_type="lore_fact", obj=fact)

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


async def _index_document(world_id: int, doc_type: str, doc_id: int, text: str) -> IndexResultInfo:
    """Index a document in vector storage, returning any warning."""
    source_type = _DOC_SOURCE_TYPE[doc_type]
    result = await vector_storage.index_document(world_id, source_type, doc_id, text)
    return IndexResultInfo(embedding_warning=result.warning if not result.indexed else None)


class ReindexWorldResult(TypedDict):
    indexed_count: int
    warning: str | None


async def reindex_world(world_id: int) -> ReindexWorldResult:
    """Reindex all documents (locations, NPCs, lore facts) for a single world."""
    await _require_world(world_id)

    locs = await locations.list_by_world(world_id)
    world_npcs = await npcs.list_by_world(world_id)
    facts = await lore_facts.list_by_world(world_id)

    count = 0
    last_warning: str | None = None

    for loc in locs:
        info = await _index_document(world_id, "location", loc.id, loc.content)
        if info["embedding_warning"]:
            last_warning = info["embedding_warning"]
        else:
            count += 1

    for npc in world_npcs:
        info = await _index_document(world_id, "npc", npc.id, npc.content)
        if info["embedding_warning"]:
            last_warning = info["embedding_warning"]
        else:
            count += 1

    for fact in facts:
        info = await _index_document(world_id, "lore_fact", fact.id, fact.content)
        if info["embedding_warning"]:
            last_warning = info["embedding_warning"]
        else:
            count += 1

    return ReindexWorldResult(indexed_count=count, warning=last_warning)


# ── Worlds CRUD ───────────────────────────────────────────────────

async def list_worlds(user_id: int | None = None, is_admin: bool = False) -> list[World]:
    """List worlds. Non-admin users get filtered view (no others' private worlds)."""
    if is_admin or user_id is None:
        return await worlds.list_all()
    return await worlds.list_for_user(user_id)


class WorldDetailData(TypedDict):
    world: World
    stats: list[WorldStatDefinition]
    rules: list[WorldRule]
    location_count: int
    npc_count: int
    lore_fact_count: int


async def get_world_detail(world_id: int) -> WorldDetailData:
    world = await _require_world(world_id)
    world_stats = await stat_defs.list_by_world(world_id)
    world_rules = await rules.list_by_world(world_id)
    locs = await locations.list_by_world(world_id)
    world_npcs = await npcs.list_by_world(world_id)
    facts = await lore_facts.list_by_world(world_id)
    return WorldDetailData(
        world=world,
        stats=world_stats,
        rules=world_rules,
        location_count=len(locs),
        npc_count=len(world_npcs),
        lore_fact_count=len(facts),
    )


def _validate_pipeline_json(pipeline_json: str) -> None:
    from app.models.schemas.pipeline import PipelineConfig
    from app.services.prompts.tool_catalog import ALL_TOOL_NAMES
    try:
        config = PipelineConfig.model_validate_json(pipeline_json)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid pipeline config: {e}",
        )
    for i, stage in enumerate(config.stages):
        if stage.step_type not in ("tool", "writer", "planning", "writing"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Stage {i}: invalid step_type '{stage.step_type}'",
            )
        invalid = set(stage.tools) - ALL_TOOL_NAMES
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Stage {i}: unknown tools: {sorted(invalid)}",
            )


def _validate_simple_tools(simple_tools_json: str) -> None:
    import json as _json
    from app.services.prompts.tool_catalog import ALL_TOOL_NAMES
    try:
        tools = _json.loads(simple_tools_json)
    except _json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid simple_tools JSON: {e}",
        )
    if not isinstance(tools, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="simple_tools must be a JSON array",
        )
    invalid = set(tools) - ALL_TOOL_NAMES
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown simple_tools: {sorted(invalid)}",
        )


async def create_world(req: CreateWorldRequest, owner_id: int | None = None) -> World:
    if req.status:
        _validate_status(req.status)
    if req.generation_mode not in _VALID_GENERATION_MODES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid generation_mode: {req.generation_mode}")
    if req.generation_mode == "agentic":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agentic mode is not implemented yet")
    if req.pipeline and req.pipeline != "{}":
        _validate_pipeline_json(req.pipeline)
    if req.simple_tools and req.simple_tools != "[]":
        _validate_simple_tools(req.simple_tools)
    now = _now()
    world = World(
        id=generate_id(),
        name=req.name,
        description=req.description,
        lore=req.lore,
        system_prompt=req.system_prompt,
        simple_tools=req.simple_tools,
        character_template=req.character_template,
        initial_message=req.initial_message,
        pipeline=req.pipeline,
        generation_mode=req.generation_mode,
        agent_config=req.agent_config,
        status=WorldStatus(req.status),
        owner_id=owner_id,
        created_at=now,
        modified_at=now,
    )
    return await worlds.create(world)


async def update_world(world_id: int, req: UpdateWorldRequest) -> World:
    world = await _require_world(world_id)
    if req.name is not None:
        world.name = req.name
    if req.description is not None:
        world.description = req.description
    if req.lore is not None:
        world.lore = req.lore
    if req.system_prompt is not None:
        world.system_prompt = req.system_prompt
    if req.simple_tools is not None:
        if req.simple_tools != "[]":
            _validate_simple_tools(req.simple_tools)
        world.simple_tools = req.simple_tools
    if req.character_template is not None:
        world.character_template = req.character_template
    if req.initial_message is not None:
        world.initial_message = req.initial_message
    if req.pipeline is not None:
        if req.pipeline and req.pipeline != "{}":
            _validate_pipeline_json(req.pipeline)
        world.pipeline = req.pipeline
    if req.generation_mode is not None:
        if req.generation_mode not in _VALID_GENERATION_MODES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid generation_mode: {req.generation_mode}")
        if req.generation_mode == "agentic":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agentic mode is not implemented yet")
        world.generation_mode = req.generation_mode
    if req.agent_config is not None:
        world.agent_config = req.agent_config
    if req.status is not None:
        _validate_status(req.status)
        world.status = WorldStatus(req.status)
    world.modified_at = _now()
    await worlds.update(world)
    return world


async def clone_world(world_id: int, owner_id: int | None = None) -> World:
    """Deep-copy a world with all child records, remapping IDs."""
    detail = await get_world_detail(world_id)
    src = detail["world"]

    # Clone world — preserve privacy: if source is private, clone is private too
    now = _now()
    clone_status = WorldStatus.private if src.status == WorldStatus.private else WorldStatus.draft
    new_world = World(
        id=generate_id(),
        name=f"{src.name} (copy)",
        description=src.description,
        lore=src.lore,
        system_prompt=src.system_prompt,
        character_template=src.character_template,
        initial_message=src.initial_message,
        pipeline=src.pipeline,
        generation_mode=src.generation_mode,
        agent_config=src.agent_config,
        status=clone_status,
        owner_id=owner_id,
        created_at=now,
        modified_at=now,
    )
    new_world = await worlds.create(new_world)
    new_wid = new_world.id

    # Clone locations with ID mapping
    loc_id_map: dict[int, int] = {}
    src_locs = await locations.list_by_world(world_id)
    for loc in src_locs:
        new_id = generate_id()
        loc_id_map[loc.id] = new_id
        new_loc = WorldLocation(
            id=new_id, world_id=new_wid, name=loc.name, content=loc.content,
            exits=None,  # remap after all locations exist
            created_at=now, modified_at=now,
        )
        await locations.create(new_loc)

    # Remap exits
    for loc in src_locs:
        if not loc.exits:
            continue
        try:
            old_exit_ids = json.loads(loc.exits)
        except (json.JSONDecodeError, TypeError):
            continue
        new_exit_ids = [loc_id_map.get(eid, eid) for eid in old_exit_ids]
        new_loc_obj = await locations.get_by_id(loc_id_map[loc.id])
        if new_loc_obj:
            new_loc_obj.exits = json.dumps(new_exit_ids)
            await locations.update(new_loc_obj)

    # Clone NPCs with ID mapping
    npc_id_map: dict[int, int] = {}
    src_npcs = await npcs.list_by_world(world_id)
    for npc in src_npcs:
        new_id = generate_id()
        npc_id_map[npc.id] = new_id
        new_npc = WorldNPC(
            id=new_id, world_id=new_wid, name=npc.name, content=npc.content,
            created_at=now, modified_at=now,
        )
        await npcs.create(new_npc)

    # Clone lore facts
    src_facts = await lore_facts.list_by_world(world_id)
    for fact in src_facts:
        new_fact = WorldLoreFact(
            id=generate_id(), world_id=new_wid, content=fact.content,
            is_injected=fact.is_injected, weight=fact.weight,
            created_at=now, modified_at=now,
        )
        await lore_facts.create(new_fact)

    # Clone NPC-location links with remapped IDs
    src_links = await npc_links.list_by_world(world_id)
    for link in src_links:
        new_npc_id = npc_id_map.get(link.npc_id)
        new_loc_id = loc_id_map.get(link.location_id)
        if new_npc_id is not None and new_loc_id is not None:
            new_link = NPCLocationLink(
                id=generate_id(), npc_id=new_npc_id, location_id=new_loc_id,
                link_type=link.link_type,
            )
            await npc_links.create(new_link)

    # Clone stats
    for stat in detail["stats"]:
        new_stat = WorldStatDefinition(
            id=generate_id(), world_id=new_wid, name=stat.name,
            description=stat.description, scope=stat.scope, stat_type=stat.stat_type,
            default_value=stat.default_value, min_value=stat.min_value,
            max_value=stat.max_value, enum_values=stat.enum_values,
            hidden=stat.hidden,
        )
        await stat_defs.create(new_stat)

    # Clone rules
    for rule in detail["rules"]:
        new_rule = WorldRule(
            id=generate_id(), world_id=new_wid,
            rule_text=rule.rule_text, order=rule.order,
        )
        await rules.create(new_rule)

    return new_world


async def delete_world(world_id: int) -> None:
    """Cascade delete: links → npcs → locations → lore_facts → stats → rules → vectors → world."""
    await _require_world(world_id)
    await npc_links.delete_by_world(world_id)
    await npcs.delete_by_world(world_id)
    await locations.delete_by_world(world_id)
    await lore_facts.delete_by_world(world_id)
    await stat_defs.delete_by_world(world_id)
    await rules.delete_by_world(world_id)
    await vector_storage.delete_world_index(world_id)
    await worlds.delete(world_id)
    logger.info("Deleted world %d with all child records", world_id)


# ── Documents (unified facade) ───────────────────────────────────

class DocumentWithMeta(TypedDict):
    doc_type: str
    obj: WorldLocation | WorldNPC | WorldLoreFact


async def list_documents(world_id: int, doc_type: str | None = None) -> list[DocumentWithMeta]:
    await _require_world(world_id)
    result: list[DocumentWithMeta] = []

    if doc_type is None or doc_type == "location":
        for loc in await locations.list_by_world(world_id):
            result.append(DocumentWithMeta(doc_type="location", obj=loc))
    if doc_type is None or doc_type == "npc":
        for npc in await npcs.list_by_world(world_id):
            result.append(DocumentWithMeta(doc_type="npc", obj=npc))
    if doc_type is None or doc_type == "lore_fact":
        for fact in await lore_facts.list_by_world(world_id):
            result.append(DocumentWithMeta(doc_type="lore_fact", obj=fact))

    return result


class DocumentDetail(TypedDict):
    doc_type: str
    obj: WorldLocation | WorldNPC | WorldLoreFact
    npc_links_list: list[NPCLocationLink] | None
    location_links_list: list[NPCLocationLink] | None


async def get_document(world_id: int, doc_id: int) -> DocumentDetail:
    await _require_world(world_id)
    doc_data = await _find_document(doc_id)
    obj = doc_data["obj"]

    # Verify document belongs to this world
    if hasattr(obj, "world_id") and obj.world_id != world_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found in this world")

    npc_links_list: list[NPCLocationLink] | None = None
    location_links_list: list[NPCLocationLink] | None = None

    if doc_data["doc_type"] == "npc":
        npc_links_list = await npc_links.list_by_npc(obj.id)
    elif doc_data["doc_type"] == "location":
        location_links_list = await npc_links.list_by_location(obj.id)

    return DocumentDetail(
        doc_type=doc_data["doc_type"],
        obj=obj,
        npc_links_list=npc_links_list,
        location_links_list=location_links_list,
    )


class DocumentSaveResult(TypedDict):
    doc_type: str
    obj: WorldLocation | WorldNPC | WorldLoreFact
    embedding_warning: str | None


async def create_document(world_id: int, req: CreateDocumentRequest) -> DocumentSaveResult:
    _validate_doc_type(req.doc_type)
    await _require_world(world_id)
    now = _now()
    new_id = generate_id()

    if req.doc_type == "location":
        exits_json = json.dumps(req.exits) if req.exits else None
        obj: WorldLocation | WorldNPC | WorldLoreFact = await locations.create(WorldLocation(
            id=new_id, world_id=world_id, name=req.name or "",
            content=req.content, exits=exits_json, created_at=now, modified_at=now,
        ))
    elif req.doc_type == "npc":
        obj = await npcs.create(WorldNPC(
            id=new_id, world_id=world_id, name=req.name or "",
            content=req.content, created_at=now, modified_at=now,
        ))
    else:  # lore_fact
        obj = await lore_facts.create(WorldLoreFact(
            id=new_id, world_id=world_id, content=req.content,
            created_at=now, modified_at=now,
        ))

    idx = await _index_document(world_id, req.doc_type, new_id, req.content)
    return DocumentSaveResult(doc_type=req.doc_type, obj=obj, embedding_warning=idx["embedding_warning"])


async def update_document(world_id: int, doc_id: int, req: UpdateDocumentRequest) -> DocumentSaveResult:
    await _require_world(world_id)
    doc_data = await _find_document(doc_id)
    obj = doc_data["obj"]
    doc_type = doc_data["doc_type"]

    if hasattr(obj, "world_id") and obj.world_id != world_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found in this world")

    if req.content is not None:
        obj.content = req.content

    if doc_type == "location":
        assert isinstance(obj, WorldLocation)
        if req.name is not None:
            obj.name = req.name
        if req.exits is not None:
            obj.exits = json.dumps(req.exits)
        obj.modified_at = _now()
        await locations.update(obj)
    elif doc_type == "npc":
        assert isinstance(obj, WorldNPC)
        if req.name is not None:
            obj.name = req.name
        obj.modified_at = _now()
        await npcs.update(obj)
    else:  # lore_fact
        assert isinstance(obj, WorldLoreFact)
        if req.is_injected is not None:
            obj.is_injected = req.is_injected
        if req.weight is not None:
            obj.weight = req.weight
        obj.modified_at = _now()
        await lore_facts.update(obj)

    idx = await _index_document(world_id, doc_type, doc_id, obj.content)
    return DocumentSaveResult(doc_type=doc_type, obj=obj, embedding_warning=idx["embedding_warning"])


async def delete_document(world_id: int, doc_id: int) -> None:
    await _require_world(world_id)
    doc_data = await _find_document(doc_id)
    obj = doc_data["obj"]
    doc_type = doc_data["doc_type"]

    if hasattr(obj, "world_id") and obj.world_id != world_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found in this world")

    # Delete links first for NPCs
    if doc_type == "npc":
        await npc_links.delete_by_npc(doc_id)

    # Delete from DB
    if doc_type == "location":
        await locations.delete(doc_id)
    elif doc_type == "npc":
        await npcs.delete(doc_id)
    else:
        await lore_facts.delete(doc_id)

    # Delete from vector index
    await vector_storage.delete_document(_DOC_SOURCE_TYPE[doc_type], doc_id)


# ── Document Upload/Download ─────────────────────────────────────

async def upload_documents(
    world_id: int, files: list[tuple[str, str]], doc_type: str
) -> list[DocumentSaveResult]:
    """Upload markdown files. files is list of (filename, content). Upsert by name."""
    _validate_doc_type(doc_type)
    await _require_world(world_id)

    if doc_type == "lore_fact":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload is not supported for lore_fact type (no name to match on)",
        )

    # Get existing docs for name matching
    existing: dict[str, int] = {}
    if doc_type == "location":
        for loc in await locations.list_by_world(world_id):
            existing[loc.name.lower()] = loc.id
    elif doc_type == "npc":
        for npc in await npcs.list_by_world(world_id):
            existing[npc.name.lower()] = npc.id

    results: list[DocumentSaveResult] = []
    for filename, content in files:
        name = filename.rsplit(".", 1)[0] if "." in filename else filename
        existing_id = existing.get(name.lower())

        if existing_id is not None:
            # Update existing
            result = await update_document(world_id, existing_id, UpdateDocumentRequest(
                name=name, content=content,
            ))
        else:
            # Create new
            result = await create_document(world_id, CreateDocumentRequest(
                doc_type=doc_type, name=name, content=content,
            ))
        results.append(result)

    return results


def download_document_md(obj: WorldLocation | WorldNPC | WorldLoreFact, doc_type: str) -> tuple[str, str]:
    """Return (filename, content) for a single document."""
    if doc_type == "lore_fact":
        assert isinstance(obj, WorldLoreFact)
        return (f"lore_fact_{obj.id}.md", obj.content)
    name = getattr(obj, "name", "") or f"{doc_type}_{obj.id}"
    return (f"{name}.md", obj.content)


async def download_documents_zip(
    world_id: int, doc_ids: list[int] | None = None, doc_type: str | None = None
) -> bytes:
    """Build a zip of markdown documents."""
    docs = await list_documents(world_id, doc_type)

    if doc_ids is not None:
        id_set = set(doc_ids)
        docs = [d for d in docs if d["obj"].id in id_set]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc in docs:
            filename, content = download_document_md(doc["obj"], doc["doc_type"])
            zf.writestr(filename, content)

    return buf.getvalue()


# ── Stats CRUD ────────────────────────────────────────────────────

async def list_stats(world_id: int) -> list[WorldStatDefinition]:
    await _require_world(world_id)
    return await stat_defs.list_by_world(world_id)


async def create_stat(world_id: int, req: CreateStatRequest) -> WorldStatDefinition:
    await _require_world(world_id)

    if req.scope not in _VALID_SCOPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid scope: {req.scope}")
    if req.stat_type not in _VALID_STAT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid stat_type: {req.stat_type}")

    enum_json = json.dumps(req.enum_values) if req.enum_values else None
    return await stat_defs.create(WorldStatDefinition(
        id=generate_id(), world_id=world_id, name=req.name,
        description=req.description, scope=StatScope(req.scope),
        stat_type=StatType(req.stat_type), default_value=req.default_value,
        min_value=req.min_value, max_value=req.max_value, enum_values=enum_json,
        hidden=req.hidden,
    ))


async def update_stat(world_id: int, stat_id: int, req: UpdateStatRequest) -> WorldStatDefinition:
    await _require_world(world_id)
    stat = await stat_defs.get_by_id(stat_id)
    if stat is None or stat.world_id != world_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stat definition not found")

    if req.name is not None:
        stat.name = req.name
    if req.description is not None:
        stat.description = req.description
    if req.scope is not None:
        if req.scope not in _VALID_SCOPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid scope: {req.scope}")
        stat.scope = StatScope(req.scope)
    if req.stat_type is not None:
        if req.stat_type not in _VALID_STAT_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid stat_type: {req.stat_type}")
        stat.stat_type = StatType(req.stat_type)
    if req.default_value is not None:
        stat.default_value = req.default_value
    if req.min_value is not None:
        stat.min_value = req.min_value
    if req.max_value is not None:
        stat.max_value = req.max_value
    if req.enum_values is not None:
        stat.enum_values = json.dumps(req.enum_values)
    if req.hidden is not None:
        stat.hidden = req.hidden

    await stat_defs.update(stat)
    return stat


async def delete_stat(world_id: int, stat_id: int) -> None:
    await _require_world(world_id)
    stat = await stat_defs.get_by_id(stat_id)
    if stat is None or stat.world_id != world_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stat definition not found")
    await stat_defs.delete(stat_id)


# ── Rules CRUD ────────────────────────────────────────────────────

async def list_rules(world_id: int) -> list[WorldRule]:
    await _require_world(world_id)
    return await rules.list_by_world(world_id)


async def create_rule(world_id: int, req: CreateRuleRequest) -> WorldRule:
    await _require_world(world_id)
    # Auto-assign order if not given
    order = req.order
    if order is None:
        existing = await rules.list_by_world(world_id)
        order = max((r.order for r in existing), default=-1) + 1

    return await rules.create(WorldRule(
        id=generate_id(), world_id=world_id,
        rule_text=req.rule_text, order=order,
    ))


async def update_rule(world_id: int, rule_id: int, req: UpdateRuleRequest) -> WorldRule:
    await _require_world(world_id)
    rule = await rules.get_by_id(rule_id)
    if rule is None or rule.world_id != world_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    if req.rule_text is not None:
        rule.rule_text = req.rule_text
    if req.order is not None:
        rule.order = req.order

    await rules.update(rule)
    return rule


async def delete_rule(world_id: int, rule_id: int) -> None:
    await _require_world(world_id)
    rule = await rules.get_by_id(rule_id)
    if rule is None or rule.world_id != world_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    await rules.delete(rule_id)


async def reorder_rules(world_id: int, rule_ids: list[int]) -> list[WorldRule]:
    await _require_world(world_id)
    for idx, rid in enumerate(rule_ids):
        rule = await rules.get_by_id(rid)
        if rule is None or rule.world_id != world_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule {rid} not found")
        rule.order = idx
        await rules.update(rule)
    return await rules.list_by_world(world_id)


# ── NPC-Location Links ───────────────────────────────────────────

class LinkWithNames(TypedDict):
    link: NPCLocationLink
    npc_name: str
    location_name: str


async def list_links(world_id: int) -> list[LinkWithNames]:
    await _require_world(world_id)
    all_links = await npc_links.list_by_world(world_id)

    # Build name maps
    world_npcs = await npcs.list_by_world(world_id)
    world_locs = await locations.list_by_world(world_id)
    npc_names = {n.id: n.name for n in world_npcs}
    loc_names = {l.id: l.name for l in world_locs}

    return [
        LinkWithNames(
            link=link,
            npc_name=npc_names.get(link.npc_id, ""),
            location_name=loc_names.get(link.location_id, ""),
        )
        for link in all_links
    ]


async def create_link(world_id: int, req: CreateNpcLocationLinkRequest) -> LinkWithNames:
    await _require_world(world_id)

    if req.link_type not in _VALID_LINK_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid link_type: {req.link_type}")

    npc_id = int(req.npc_id)
    location_id = int(req.location_id)

    npc = await npcs.get_by_id(npc_id)
    if npc is None or npc.world_id != world_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NPC not found in this world")

    loc = await locations.get_by_id(location_id)
    if loc is None or loc.world_id != world_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found in this world")

    link = await npc_links.create(NPCLocationLink(
        id=generate_id(), npc_id=npc_id, location_id=location_id,
        link_type=NPCLinkType(req.link_type),
    ))

    return LinkWithNames(link=link, npc_name=npc.name, location_name=loc.name)


async def delete_link(world_id: int, link_id: int) -> None:
    await _require_world(world_id)
    link = await npc_links.get_by_id(link_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    # Verify link belongs to this world (through NPC)
    npc = await npcs.get_by_id(link.npc_id)
    if npc is None or npc.world_id != world_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found in this world")
    await npc_links.delete(link_id)
