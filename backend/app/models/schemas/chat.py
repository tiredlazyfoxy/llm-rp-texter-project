"""Pydantic request/response schemas for chat sessions."""

from pydantic import BaseModel


class ModelConfig(BaseModel):
    model_id: str | None = None
    temperature: float = 0.7
    repeat_penalty: float = 1.0
    top_p: float = 1.0


class CreateChatRequest(BaseModel):
    world_id: str
    character_name: str
    template_variables: dict[str, str]
    starting_location_id: str
    tool_model: ModelConfig
    text_model: ModelConfig


class SendMessageRequest(BaseModel):
    content: str


class ContinueRequest(BaseModel):
    selected_variant_id: str


class RewindRequest(BaseModel):
    target_turn: int


class UpdateChatSettingsRequest(BaseModel):
    tool_model: ModelConfig | None = None
    text_model: ModelConfig | None = None
    user_instructions: str | None = None


class ChatSessionResponse(BaseModel):
    id: str
    world_id: str
    world_name: str
    character_name: str
    character_description: str
    character_stats: dict[str, int | str | list[str]]
    world_stats: dict[str, int | str | list[str]]
    current_location_id: str | None
    current_location_name: str | None
    current_turn: int
    status: str
    tool_model: ModelConfig
    text_model: ModelConfig
    user_instructions: str
    created_at: str
    modified_at: str


class ChatSessionListItem(BaseModel):
    id: str
    world_id: str
    world_name: str
    character_name: str
    current_turn: int
    status: str
    modified_at: str


class ChatSessionListResponse(BaseModel):
    items: list[ChatSessionListItem]


class ToolCallInfo(BaseModel):
    tool_name: str
    arguments: dict[str, str]
    result: str


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    turn_number: int
    tool_calls: list[ToolCallInfo] | None
    generation_plan: str | None = None
    thinking_content: str | None = None
    is_active_variant: bool
    created_at: str


class ChatStateSnapshotResponse(BaseModel):
    turn_number: int
    location_id: str | None
    location_name: str | None
    character_stats: dict[str, int | str | list[str]]
    world_stats: dict[str, int | str | list[str]]


class ChatDetailResponse(BaseModel):
    session: ChatSessionResponse
    messages: list[ChatMessageResponse]
    snapshots: list[ChatStateSnapshotResponse]
    variants: list[ChatMessageResponse]
    summaries: list["ChatSummaryResponse"] = []


class LocationBrief(BaseModel):
    id: str
    name: str


class StatDefinitionResponse(BaseModel):
    name: str
    description: str
    scope: str
    stat_type: str
    default_value: str
    min_value: int | None
    max_value: int | None
    enum_values: list[str] | None
    hidden: bool


class WorldInfoResponse(BaseModel):
    id: str
    name: str
    description: str
    lore: str
    character_template: str
    generation_mode: str
    locations: list[LocationBrief]
    stat_definitions: list[StatDefinitionResponse]


class ChatSummaryResponse(BaseModel):
    id: str
    start_message_id: str
    end_message_id: str
    start_turn: int
    end_turn: int
    content: str
    created_at: str


class EditMessageRequest(BaseModel):
    content: str


class RegenerateRequest(BaseModel):
    turn_number: int | None = None


class CompactRequest(BaseModel):
    up_to_message_id: str


class CompactResponse(BaseModel):
    summary: ChatSummaryResponse
    updated_message_count: int
