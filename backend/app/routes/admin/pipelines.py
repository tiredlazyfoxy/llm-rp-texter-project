"""Admin pipeline endpoints — shared pipeline CRUD + static config options."""

from fastapi import APIRouter, Depends, status

from app.models.pipeline import Pipeline
from app.models.schemas.pipeline import (
    CreatePipelineRequest,
    PipelineResponse,
    PipelinesListResponse,
    UpdatePipelineRequest,
)
from app.models.schemas.worlds import PipelineConfigOptionsResponse
from app.models.user import User, UserRole
from app.services import pipelines as svc
from app.services.auth import require_role

_require_editor = require_role(UserRole.editor)
_require_admin = require_role(UserRole.admin)

router = APIRouter(prefix="/api/admin/pipelines", tags=["admin-pipelines"])


def _pipeline_to_response(p: Pipeline) -> PipelineResponse:
    return PipelineResponse(
        id=str(p.id),
        name=p.name,
        description=p.description,
        kind=p.kind.value,
        system_prompt=p.system_prompt,
        simple_tools=p.simple_tools,
        pipeline_config=p.pipeline_config,
        agent_config=p.agent_config,
        created_at=p.created_at,
        modified_at=p.modified_at,
    )


@router.get("", response_model=PipelinesListResponse)
async def list_pipelines(_caller: User = Depends(_require_editor)):
    items = await svc.list_pipelines()
    return PipelinesListResponse(items=[_pipeline_to_response(p) for p in items])


@router.get("/config-options", response_model=PipelineConfigOptionsResponse)
async def get_config_options(_caller: User = Depends(_require_editor)):
    """Return static pipeline configuration options (placeholders, tools, default templates)."""
    from app.services.prompts.placeholder_registry import PLACEHOLDER_REGISTRY
    from app.services.prompts.tool_catalog import TOOL_CATALOG
    from app.services.prompts.default_templates import (
        DEFAULT_DIRECTOR_PROMPT,
        DEFAULT_SIMPLE_PROMPT,
        DEFAULT_TOOL_PROMPT,
        DEFAULT_WRITER_PROMPT,
    )
    return PipelineConfigOptionsResponse(
        placeholders=PLACEHOLDER_REGISTRY,  # type: ignore[arg-type]
        tools=TOOL_CATALOG,  # type: ignore[arg-type]
        default_templates={
            "simple": DEFAULT_SIMPLE_PROMPT,
            "tool": DEFAULT_TOOL_PROMPT,
            "writer": DEFAULT_WRITER_PROMPT,
            "director": DEFAULT_DIRECTOR_PROMPT,
        },
    )


@router.post("", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(req: CreatePipelineRequest, _caller: User = Depends(_require_editor)):
    pipeline = await svc.create_pipeline(req)
    return _pipeline_to_response(pipeline)


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(pipeline_id: int, _caller: User = Depends(_require_editor)):
    pipeline = await svc.get_pipeline(pipeline_id)
    return _pipeline_to_response(pipeline)


@router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: int, req: UpdatePipelineRequest, _caller: User = Depends(_require_editor)
):
    pipeline = await svc.update_pipeline(pipeline_id, req)
    return _pipeline_to_response(pipeline)


@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(pipeline_id: int, _caller: User = Depends(_require_admin)):
    await svc.delete_pipeline(pipeline_id)
