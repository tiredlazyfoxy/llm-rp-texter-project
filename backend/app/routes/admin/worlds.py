"""Admin world editor endpoints — worlds, documents, stats, rules, NPC-location links."""

import json

from fastapi import APIRouter, Depends, Query, UploadFile, status
from fastapi.responses import Response

from app.models.schemas.worlds import (
    CreateDocumentRequest,
    CreateNpcLocationLinkRequest,
    CreateRuleRequest,
    CreateStatRequest,
    CreateWorldRequest,
    DocumentResponse,
    DocumentSaveResponse,
    DocumentsListResponse,
    LinkedNpcInfo,
    NpcLinkInfo,
    NpcLocationLinkResponse,
    NpcLocationLinksListResponse,
    ReorderRulesRequest,
    RuleResponse,
    StatDefinitionResponse,
    UpdateDocumentRequest,
    UpdateRuleRequest,
    UpdateStatRequest,
    UpdateWorldRequest,
    WorldDetailResponse,
    WorldResponse,
    WorldsListResponse,
)
from app.models.user import User, UserRole
from app.models.world import (
    World,
    WorldLocation,
    WorldLoreFact,
    WorldNPC,
    WorldRule,
    WorldStatDefinition,
)
from app.services import world_editor as svc
from app.services.auth import require_role

_require_editor = require_role(UserRole.editor)
_require_admin = require_role(UserRole.admin)

router = APIRouter(prefix="/api/admin/worlds", tags=["admin-worlds"])


# ── Conversion helpers ────────────────────────────────────────────

def _world_to_response(w: World) -> WorldResponse:
    return WorldResponse(
        id=str(w.id), name=w.name, description=w.description, lore=w.lore,
        system_prompt=w.system_prompt, character_template=w.character_template,
        initial_message=w.initial_message, pipeline=w.pipeline,
        status=w.status.value, created_at=w.created_at, modified_at=w.modified_at,
    )


def _stat_to_response(s: WorldStatDefinition) -> StatDefinitionResponse:
    enum_vals: list[str] | None = None
    if s.enum_values:
        try:
            enum_vals = json.loads(s.enum_values)
        except (json.JSONDecodeError, TypeError):
            enum_vals = None
    return StatDefinitionResponse(
        id=str(s.id), world_id=str(s.world_id), name=s.name,
        description=s.description, scope=s.scope.value, stat_type=s.stat_type.value,
        default_value=s.default_value, min_value=s.min_value, max_value=s.max_value,
        enum_values=enum_vals,
    )


def _rule_to_response(r: WorldRule) -> RuleResponse:
    return RuleResponse(
        id=str(r.id), world_id=str(r.world_id),
        rule_text=r.rule_text, order=r.order,
    )


def _doc_to_response(
    obj: WorldLocation | WorldNPC | WorldLoreFact,
    doc_type: str,
    npc_links_list: list | None = None,
    location_links_list: list | None = None,
) -> DocumentResponse:
    name: str | None = getattr(obj, "name", None)
    exits: list[str] | None = None
    links: list[NpcLinkInfo] | None = None
    linked_npcs: list[LinkedNpcInfo] | None = None

    if doc_type == "location" and isinstance(obj, WorldLocation):
        if obj.exits:
            try:
                exits = [str(eid) for eid in json.loads(obj.exits)]
            except (json.JSONDecodeError, TypeError):
                exits = None

    if npc_links_list is not None:
        links = [
            NpcLinkInfo(
                link_id=str(lnk.id), location_id=str(lnk.location_id),
                location_name=getattr(lnk, "_location_name", ""),
                link_type=lnk.link_type.value,
            )
            for lnk in npc_links_list
        ]

    if location_links_list is not None:
        linked_npcs = [
            LinkedNpcInfo(
                link_id=str(lnk.id), npc_id=str(lnk.npc_id),
                npc_name=getattr(lnk, "_npc_name", ""),
                link_type=lnk.link_type.value,
            )
            for lnk in location_links_list
        ]

    return DocumentResponse(
        id=str(obj.id), doc_type=doc_type, world_id=str(obj.world_id),
        name=name, content=obj.content,
        created_at=obj.created_at, modified_at=obj.modified_at,
        exits=exits, links=links, linked_npcs=linked_npcs,
    )


async def _enrich_doc_response(detail: svc.DocumentDetail) -> DocumentResponse:
    """Build DocumentResponse with enriched link names."""
    from app.db import locations, npcs

    npc_links_list = detail.get("npc_links_list")
    location_links_list = detail.get("location_links_list")

    # Enrich NPC link names (NPC's location links: need location names)
    if npc_links_list:
        for lnk in npc_links_list:
            loc = await locations.get_by_id(lnk.location_id)
            lnk._location_name = loc.name if loc else ""  # type: ignore[attr-defined]

    # Enrich location link names (location's NPC links: need NPC names)
    if location_links_list:
        for lnk in location_links_list:
            npc = await npcs.get_by_id(lnk.npc_id)
            lnk._npc_name = npc.name if npc else ""  # type: ignore[attr-defined]

    return _doc_to_response(
        detail["obj"], detail["doc_type"],
        npc_links_list=npc_links_list,
        location_links_list=location_links_list,
    )


# ── Worlds ────────────────────────────────────────────────────────

@router.get("", response_model=WorldsListResponse)
async def list_worlds(_caller: User = Depends(_require_editor)):
    worlds = await svc.list_worlds()
    return WorldsListResponse(items=[_world_to_response(w) for w in worlds])


@router.post("", response_model=WorldResponse, status_code=status.HTTP_201_CREATED)
async def create_world(req: CreateWorldRequest, _caller: User = Depends(_require_editor)):
    world = await svc.create_world(req)
    return _world_to_response(world)


@router.get("/{world_id}", response_model=WorldDetailResponse)
async def get_world(world_id: int, _caller: User = Depends(_require_editor)):
    detail = await svc.get_world_detail(world_id)
    w = detail["world"]
    resp = WorldDetailResponse(
        id=str(w.id), name=w.name, description=w.description, lore=w.lore,
        system_prompt=w.system_prompt, character_template=w.character_template,
        initial_message=w.initial_message, pipeline=w.pipeline,
        status=w.status.value, created_at=w.created_at, modified_at=w.modified_at,
        stats=[_stat_to_response(s) for s in detail["stats"]],
        rules=[_rule_to_response(r) for r in detail["rules"]],
        location_count=detail["location_count"],
        npc_count=detail["npc_count"],
        lore_fact_count=detail["lore_fact_count"],
    )
    return resp


@router.put("/{world_id}", response_model=WorldResponse)
async def update_world(world_id: int, req: UpdateWorldRequest, _caller: User = Depends(_require_editor)):
    world = await svc.update_world(world_id, req)
    return _world_to_response(world)


@router.post("/{world_id}/clone", response_model=WorldResponse, status_code=status.HTTP_201_CREATED)
async def clone_world(world_id: int, _caller: User = Depends(_require_editor)):
    world = await svc.clone_world(world_id)
    return _world_to_response(world)


@router.delete("/{world_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_world(world_id: int, _caller: User = Depends(_require_admin)):
    await svc.delete_world(world_id)


# ── Documents — static paths first ───────────────────────────────

@router.get("/{world_id}/documents", response_model=DocumentsListResponse)
async def list_documents(
    world_id: int,
    doc_type: str | None = Query(None),
    _caller: User = Depends(_require_editor),
):
    docs = await svc.list_documents(world_id, doc_type)
    return DocumentsListResponse(items=[
        _doc_to_response(d["obj"], d["doc_type"]) for d in docs
    ])


@router.post("/{world_id}/documents", response_model=DocumentSaveResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    world_id: int, req: CreateDocumentRequest, _caller: User = Depends(_require_editor),
):
    result = await svc.create_document(world_id, req)
    resp = _doc_to_response(result["obj"], result["doc_type"])
    return DocumentSaveResponse(
        **resp.model_dump(), embedding_warning=result["embedding_warning"],
    )


@router.post("/{world_id}/documents/upload", response_model=list[DocumentSaveResponse])
async def upload_documents(
    world_id: int,
    files: list[UploadFile],
    doc_type: str = Query(...),
    _caller: User = Depends(_require_editor),
):
    file_data: list[tuple[str, str]] = []
    for f in files:
        content = (await f.read()).decode("utf-8")
        file_data.append((f.filename or "untitled.md", content))

    results = await svc.upload_documents(world_id, file_data, doc_type)
    responses: list[DocumentSaveResponse] = []
    for r in results:
        resp = _doc_to_response(r["obj"], r["doc_type"])
        responses.append(DocumentSaveResponse(
            **resp.model_dump(), embedding_warning=r["embedding_warning"],
        ))
    return responses


@router.get("/{world_id}/documents/download-all")
async def download_all_documents(world_id: int, _caller: User = Depends(_require_editor)):
    zip_bytes = await svc.download_documents_zip(world_id)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=world_{world_id}_documents.zip"},
    )


@router.post("/{world_id}/documents/download")
async def download_selected_documents(
    world_id: int,
    doc_ids: list[str],
    _caller: User = Depends(_require_editor),
):
    int_ids = [int(did) for did in doc_ids]
    zip_bytes = await svc.download_documents_zip(world_id, doc_ids=int_ids)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=world_{world_id}_documents.zip"},
    )


@router.get("/{world_id}/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(world_id: int, doc_id: int, _caller: User = Depends(_require_editor)):
    detail = await svc.get_document(world_id, doc_id)
    return await _enrich_doc_response(detail)


@router.put("/{world_id}/documents/{doc_id}", response_model=DocumentSaveResponse)
async def update_document(
    world_id: int, doc_id: int, req: UpdateDocumentRequest, _caller: User = Depends(_require_editor),
):
    result = await svc.update_document(world_id, doc_id, req)
    resp = _doc_to_response(result["obj"], result["doc_type"])
    return DocumentSaveResponse(
        **resp.model_dump(), embedding_warning=result["embedding_warning"],
    )


@router.delete("/{world_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(world_id: int, doc_id: int, _caller: User = Depends(_require_editor)):
    await svc.delete_document(world_id, doc_id)


@router.get("/{world_id}/documents/{doc_id}/download")
async def download_document(world_id: int, doc_id: int, _caller: User = Depends(_require_editor)):
    detail = await svc.get_document(world_id, doc_id)
    filename, content = svc.download_document_md(detail["obj"], detail["doc_type"])
    return Response(
        content=content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


# ── Stats ─────────────────────────────────────────────────────────

@router.get("/{world_id}/stats", response_model=list[StatDefinitionResponse])
async def list_stats(world_id: int, _caller: User = Depends(_require_editor)):
    stats = await svc.list_stats(world_id)
    return [_stat_to_response(s) for s in stats]


@router.post("/{world_id}/stats", response_model=StatDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_stat(world_id: int, req: CreateStatRequest, _caller: User = Depends(_require_editor)):
    stat = await svc.create_stat(world_id, req)
    return _stat_to_response(stat)


@router.put("/{world_id}/stats/{stat_id}", response_model=StatDefinitionResponse)
async def update_stat(world_id: int, stat_id: int, req: UpdateStatRequest, _caller: User = Depends(_require_editor)):
    stat = await svc.update_stat(world_id, stat_id, req)
    return _stat_to_response(stat)


@router.delete("/{world_id}/stats/{stat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stat(world_id: int, stat_id: int, _caller: User = Depends(_require_editor)):
    await svc.delete_stat(world_id, stat_id)


# ── Rules — static paths first ───────────────────────────────────

@router.get("/{world_id}/rules", response_model=list[RuleResponse])
async def list_rules(world_id: int, _caller: User = Depends(_require_editor)):
    rule_list = await svc.list_rules(world_id)
    return [_rule_to_response(r) for r in rule_list]


@router.post("/{world_id}/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(world_id: int, req: CreateRuleRequest, _caller: User = Depends(_require_editor)):
    rule = await svc.create_rule(world_id, req)
    return _rule_to_response(rule)


@router.put("/{world_id}/rules/reorder", response_model=list[RuleResponse])
async def reorder_rules(world_id: int, req: ReorderRulesRequest, _caller: User = Depends(_require_editor)):
    int_ids = [int(rid) for rid in req.rule_ids]
    rule_list = await svc.reorder_rules(world_id, int_ids)
    return [_rule_to_response(r) for r in rule_list]


@router.put("/{world_id}/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(world_id: int, rule_id: int, req: UpdateRuleRequest, _caller: User = Depends(_require_editor)):
    rule = await svc.update_rule(world_id, rule_id, req)
    return _rule_to_response(rule)


@router.delete("/{world_id}/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(world_id: int, rule_id: int, _caller: User = Depends(_require_editor)):
    await svc.delete_rule(world_id, rule_id)


# ── NPC-Location Links ───────────────────────────────────────────

@router.get("/{world_id}/npc-location-links", response_model=NpcLocationLinksListResponse)
async def list_npc_location_links(world_id: int, _caller: User = Depends(_require_editor)):
    items = await svc.list_links(world_id)
    return NpcLocationLinksListResponse(items=[
        NpcLocationLinkResponse(
            id=str(i["link"].id), npc_id=str(i["link"].npc_id),
            npc_name=i["npc_name"], location_id=str(i["link"].location_id),
            location_name=i["location_name"], link_type=i["link"].link_type.value,
        )
        for i in items
    ])


@router.post("/{world_id}/npc-location-links", response_model=NpcLocationLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_npc_location_link(
    world_id: int, req: CreateNpcLocationLinkRequest, _caller: User = Depends(_require_editor),
):
    result = await svc.create_link(world_id, req)
    link = result["link"]
    return NpcLocationLinkResponse(
        id=str(link.id), npc_id=str(link.npc_id), npc_name=result["npc_name"],
        location_id=str(link.location_id), location_name=result["location_name"],
        link_type=link.link_type.value,
    )


@router.delete("/{world_id}/npc-location-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_npc_location_link(world_id: int, link_id: int, _caller: User = Depends(_require_editor)):
    await svc.delete_link(world_id, link_id)
