from pydantic import BaseModel


class PipelineStage(BaseModel):
    step_type: str  # "planning" | "writing"
    prompt: str = ""  # admin free-text, editable via LLM chat
    max_agent_steps: int | None = None  # only for tool-calling types (planning)


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
