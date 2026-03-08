"""LLM models endpoint — lists enabled models for editor model picker."""

from fastapi import APIRouter, Depends

from app.models.schemas.llm_servers import EnabledModelsListResponse
from app.models.user import User, UserRole
from app.services import llm_servers as llm_service
from app.services.auth import require_role

_require_editor = require_role(UserRole.editor)

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/models", response_model=EnabledModelsListResponse)
async def list_enabled_models(
    _caller: User = Depends(_require_editor),
) -> EnabledModelsListResponse:
    models = await llm_service.get_all_enabled_models()
    return EnabledModelsListResponse(models=models)
