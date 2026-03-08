from datetime import datetime

from pydantic import BaseModel


class LlmServerResponse(BaseModel):
    id: str
    name: str
    backend_type: str
    base_url: str
    has_api_key: bool
    enabled_models: list[str]
    is_active: bool
    created_at: datetime | None
    modified_at: datetime | None


class LlmServersListResponse(BaseModel):
    items: list[LlmServerResponse]


class CreateLlmServerRequest(BaseModel):
    name: str
    backend_type: str  # "llama-swap" | "openai"
    base_url: str
    api_key: str | None = None
    is_active: bool = True


class UpdateLlmServerRequest(BaseModel):
    name: str | None = None
    backend_type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    is_active: bool | None = None


class EnabledModelsRequest(BaseModel):
    enabled_models: list[str]


class AvailableModelsResponse(BaseModel):
    models: list[str]


class EnabledModelInfo(BaseModel):
    server_id: str
    server_name: str
    model_id: str


class EnabledModelsListResponse(BaseModel):
    models: list[EnabledModelInfo]
