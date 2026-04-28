from datetime import datetime

from pydantic import BaseModel


# ── World ─────────────────────────────────────────────────────────

class WorldResponse(BaseModel):
    id: str
    name: str
    description: str
    lore: str
    system_prompt: str
    simple_tools: str
    character_template: str
    initial_message: str
    pipeline: str
    generation_mode: str
    agent_config: str
    status: str
    owner_id: str | None
    created_at: datetime | None
    modified_at: datetime | None


class WorldDetailResponse(WorldResponse):
    stats: list["StatDefinitionResponse"]
    rules: list["RuleResponse"]
    location_count: int
    npc_count: int
    lore_fact_count: int


class WorldsListResponse(BaseModel):
    items: list[WorldResponse]


class CreateWorldRequest(BaseModel):
    name: str
    description: str = ""
    lore: str = ""
    system_prompt: str = ""
    simple_tools: str = "[]"
    character_template: str = ""
    initial_message: str = ""
    pipeline: str = "{}"
    generation_mode: str = "simple"
    agent_config: str = "{}"
    status: str = "draft"


class UpdateWorldRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    lore: str | None = None
    system_prompt: str | None = None
    simple_tools: str | None = None
    character_template: str | None = None
    initial_message: str | None = None
    pipeline: str | None = None
    generation_mode: str | None = None
    agent_config: str | None = None
    status: str | None = None


# ── Documents (unified) ──────────────────────────────────────────

class NpcLinkInfo(BaseModel):
    link_id: str
    location_id: str
    location_name: str
    link_type: str


class LinkedNpcInfo(BaseModel):
    link_id: str
    npc_id: str
    npc_name: str
    link_type: str


class DocumentResponse(BaseModel):
    id: str
    doc_type: str
    world_id: str
    name: str | None
    content: str
    created_at: datetime | None
    modified_at: datetime | None
    exits: list[str] | None = None
    links: list[NpcLinkInfo] | None = None
    linked_npcs: list[LinkedNpcInfo] | None = None
    is_injected: bool = False
    weight: int = 0


class DocumentSaveResponse(DocumentResponse):
    embedding_warning: str | None = None


class DocumentsListResponse(BaseModel):
    items: list[DocumentResponse]


class CreateDocumentRequest(BaseModel):
    doc_type: str  # "location" | "npc" | "lore_fact"
    name: str | None = None
    content: str = ""
    exits: list[str] | None = None


class UpdateDocumentRequest(BaseModel):
    name: str | None = None
    content: str | None = None
    exits: list[str] | None = None
    is_injected: bool | None = None
    weight: int | None = None


# ── Stats ─────────────────────────────────────────────────────────

class StatDefinitionResponse(BaseModel):
    id: str
    world_id: str
    name: str
    description: str
    scope: str
    stat_type: str
    default_value: str
    min_value: int | None
    max_value: int | None
    enum_values: list[str] | None
    hidden: bool


class CreateStatRequest(BaseModel):
    name: str
    description: str = ""
    scope: str  # "character" | "world"
    stat_type: str  # "int" | "enum" | "set"
    default_value: str = "0"
    min_value: int | None = None
    max_value: int | None = None
    enum_values: list[str] | None = None
    hidden: bool = False


class UpdateStatRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    scope: str | None = None
    stat_type: str | None = None
    default_value: str | None = None
    min_value: int | None = None
    max_value: int | None = None
    enum_values: list[str] | None = None
    hidden: bool | None = None


# ── Rules ─────────────────────────────────────────────────────────

class RuleResponse(BaseModel):
    id: str
    world_id: str
    rule_text: str
    order: int


class CreateRuleRequest(BaseModel):
    rule_text: str
    order: int | None = None


class UpdateRuleRequest(BaseModel):
    rule_text: str | None = None
    order: int | None = None


class ReorderRulesRequest(BaseModel):
    rule_ids: list[str]


# ── NPC-Location Links ───────────────────────────────────────────

class NpcLocationLinkResponse(BaseModel):
    id: str
    npc_id: str
    npc_name: str
    location_id: str
    location_name: str
    link_type: str


class NpcLocationLinksListResponse(BaseModel):
    items: list[NpcLocationLinkResponse]


class CreateNpcLocationLinkRequest(BaseModel):
    npc_id: str
    location_id: str
    link_type: str  # "present" | "excluded"


# ── Reindex ──────────────────────────────────────────────────────

class ReindexWorldResponse(BaseModel):
    indexed_count: int
    warning: str | None = None


# ── Pipeline Config ─────────────────────────────────────────────

class PlaceholderInfoResponse(BaseModel):
    name: str
    description: str
    category: str


class ToolCatalogEntryResponse(BaseModel):
    name: str
    description: str
    category: str


class DefaultTemplatesResponse(BaseModel):
    simple: str
    tool: str
    writer: str
    director: str


class PipelineConfigOptionsResponse(BaseModel):
    placeholders: list[PlaceholderInfoResponse]
    tools: list[ToolCatalogEntryResponse]
    default_templates: DefaultTemplatesResponse
