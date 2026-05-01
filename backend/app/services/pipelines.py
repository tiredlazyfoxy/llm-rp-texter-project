"""Pipeline editor — business logic for shared pipeline entities."""

import json as _json
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.db import pipelines as pipelines_db
from app.models.pipeline import Pipeline, PipelineKind
from app.models.schemas.pipeline import (
    CreatePipelineRequest,
    PipelineConfig,
    UpdatePipelineRequest,
)
from app.services.snowflake import generate_id

logger = logging.getLogger(__name__)

_VALID_KINDS = {k.value for k in PipelineKind}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_kind(kind: str) -> None:
    if kind not in _VALID_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pipeline kind: {kind}. Must be one of: {', '.join(sorted(_VALID_KINDS))}",
        )
    if kind == "agentic":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agentic mode is not implemented yet",
        )


def _validate_pipeline_config(pipeline_config_json: str) -> None:
    if not pipeline_config_json or pipeline_config_json == "{}":
        return
    from app.services.prompts.tool_catalog import ALL_TOOL_NAMES
    try:
        config = PipelineConfig.model_validate_json(pipeline_config_json)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid pipeline config: {e}",
        )
    for i, stage in enumerate(config.stages):
        if stage.step_type not in ("tool", "writer", "planning", "writing"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Stage {i}: invalid step_type '{stage.step_type}'",
            )
        invalid = set(stage.tools) - ALL_TOOL_NAMES
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Stage {i}: unknown tools: {sorted(invalid)}",
            )


def _validate_simple_tools(simple_tools_json: str) -> None:
    if not simple_tools_json or simple_tools_json == "[]":
        return
    from app.services.prompts.tool_catalog import ALL_TOOL_NAMES
    try:
        tools = _json.loads(simple_tools_json)
    except _json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid simple_tools JSON: {e}",
        )
    if not isinstance(tools, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="simple_tools must be a JSON array",
        )
    invalid = set(tools) - ALL_TOOL_NAMES
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown simple_tools: {sorted(invalid)}",
        )


async def list_pipelines() -> list[Pipeline]:
    return await pipelines_db.list_all()


async def get_pipeline(pipeline_id: int) -> Pipeline:
    pipeline = await pipelines_db.get_by_id(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    return pipeline


async def create_pipeline(req: CreatePipelineRequest) -> Pipeline:
    _validate_kind(req.kind)
    _validate_pipeline_config(req.pipeline_config)
    _validate_simple_tools(req.simple_tools)
    now = _now()
    pipeline = Pipeline(
        id=generate_id(),
        name=req.name,
        description=req.description,
        kind=PipelineKind(req.kind),
        system_prompt=req.system_prompt,
        simple_tools=req.simple_tools,
        pipeline_config=req.pipeline_config,
        agent_config=req.agent_config,
        created_at=now,
        modified_at=now,
    )
    return await pipelines_db.create(pipeline)


async def update_pipeline(pipeline_id: int, req: UpdatePipelineRequest) -> Pipeline:
    pipeline = await get_pipeline(pipeline_id)
    if req.name is not None:
        pipeline.name = req.name
    if req.description is not None:
        pipeline.description = req.description
    if req.kind is not None:
        _validate_kind(req.kind)
        pipeline.kind = PipelineKind(req.kind)
    if req.system_prompt is not None:
        pipeline.system_prompt = req.system_prompt
    if req.simple_tools is not None:
        _validate_simple_tools(req.simple_tools)
        pipeline.simple_tools = req.simple_tools
    if req.pipeline_config is not None:
        _validate_pipeline_config(req.pipeline_config)
        pipeline.pipeline_config = req.pipeline_config
    if req.agent_config is not None:
        pipeline.agent_config = req.agent_config
    pipeline.modified_at = _now()
    await pipelines_db.update(pipeline)
    return pipeline


async def delete_pipeline(pipeline_id: int) -> None:
    pipeline = await pipelines_db.get_by_id(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    if await pipelines_db.is_referenced(pipeline_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pipeline is referenced by one or more worlds",
        )
    await pipelines_db.delete(pipeline_id)
