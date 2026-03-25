from pydantic import BaseModel


class PipelineStage(BaseModel):
    step_type: str  # "tool" | "writer" (legacy: "planning" | "writing")
    prompt: str = ""  # full system prompt template with {PLACEHOLDER} syntax
    max_agent_steps: int | None = None  # only for "tool" steps
    tools: list[str] = []  # enabled tool names from tool catalog


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
