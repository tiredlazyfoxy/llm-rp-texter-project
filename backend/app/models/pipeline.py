import enum
from datetime import datetime

from sqlmodel import Field, SQLModel


class PipelineKind(str, enum.Enum):
    simple = "simple"
    chain = "chain"
    agentic = "agentic"


class Pipeline(SQLModel, table=True):
    __tablename__ = "pipelines"

    id: int = Field(primary_key=True)
    name: str = Field(index=True)
    description: str = Field(default="")
    kind: PipelineKind = Field(default=PipelineKind.simple)

    # Simple mode — used when kind == "simple"
    system_prompt: str = Field(default="")
    simple_tools: str = Field(default="[]")          # JSON list of tool names

    # Chain mode — used when kind == "chain"; JSON of PipelineConfig
    pipeline_config: str = Field(default="{}")

    # Agentic mode — used when kind == "agentic"; JSON
    agent_config: str = Field(default="{}")

    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)
