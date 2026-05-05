"""Admin id-allocation endpoints.

Single, thin endpoint that returns a freshly-generated snowflake id so the
client can pre-allocate ids before opening a draft editor."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.models.user import User, UserRole
from app.services.auth import require_role
from app.services.snowflake import generate_id

_require_editor = require_role(UserRole.editor)

router = APIRouter(prefix="/api/admin", tags=["admin-ids"])


class NewSnowflakeIdResponse(BaseModel):
    id: str


@router.get("/snowflake/new", response_model=NewSnowflakeIdResponse)
async def get_new_snowflake_id(_caller: User = Depends(_require_editor)) -> NewSnowflakeIdResponse:
    return NewSnowflakeIdResponse(id=str(generate_id()))
