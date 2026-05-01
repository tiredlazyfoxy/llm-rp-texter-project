from datetime import datetime

from pydantic import BaseModel


class PipelineStage(BaseModel):
    step_type: str  # "tool" | "writer" (legacy: "planning" | "writing")
    name: str = ""  # admin-defined stage label (e.g. "Research", "Combat")
    prompt: str = ""  # full system prompt template with {PLACEHOLDER} syntax
    max_agent_steps: int | None = None  # only for "tool" steps
    tools: list[str] = []  # enabled tool names from tool catalog
    enabled: bool = True  # disabled stages are skipped at runtime
    model_id: str | None = None  # overrides session model for this stage


class PipelineConfig(BaseModel):
    stages: list[PipelineStage] = []


class StatUpdateEntry(BaseModel):
    name: str
    value: str


class PlanningContext(BaseModel):
    """Built by planning tools during the planning LLM call.
    Converted to GenerationPlanOutput for persistence."""
    facts: list[str] = []
    decisions: list[str] = []
    stat_updates: list[StatUpdateEntry] = []


class GenerationPlanOutput(BaseModel):
    collected_data: str = ""
    stat_updates: list[StatUpdateEntry] = []
    decisions: list[str] = []


# ── Pipeline API Schemas ─────────────────────────────────────────

class PipelineResponse(BaseModel):
    id: str
    name: str
    description: str
    kind: str                         # "simple" | "chain" | "agentic"
    system_prompt: str
    simple_tools: str                 # JSON list
    pipeline_config: str              # JSON PipelineConfig
    agent_config: str                 # JSON
    created_at: datetime | None
    modified_at: datetime | None


class PipelinesListResponse(BaseModel):
    items: list[PipelineResponse]


class CreatePipelineRequest(BaseModel):
    name: str
    description: str = ""
    kind: str = "simple"
    system_prompt: str = ""
    simple_tools: str = "[]"
    pipeline_config: str = "{}"
    agent_config: str = "{}"


class UpdatePipelineRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    kind: str | None = None
    system_prompt: str | None = None
    simple_tools: str | None = None
    pipeline_config: str | None = None
    agent_config: str | None = None
