from datetime import datetime

from sqlmodel import Field, SQLModel


class LlmServer(SQLModel, table=True):
    __tablename__ = "llm_servers"

    id: int = Field(primary_key=True)  # snowflake int64
    name: str
    backend_type: str  # "llama-swap" | "openai"
    base_url: str
    api_key: str | None = None
    enabled_models: str = "[]"  # JSON array of model ID strings
    is_active: bool = True
    is_embedding: bool = False
    embedding_model: str | None = None  # model ID on this server used for embeddings
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)
