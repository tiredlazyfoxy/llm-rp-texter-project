"""Admin user management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas.admin import (
    AdminCreateUserRequest,
    AdminSetPasswordRequest,
    AdminSetRoleRequest,
    AdminUserResponse,
)
from app.models.user import User, UserRole
from app.services import admin as admin_service
from app.services.auth import require_role

_require_admin = require_role(UserRole.admin)

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


def _to_response(user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=str(user.id),
        username=user.username,
        role=user.role,
        last_login=user.last_login,
    )


@router.get("", response_model=list[AdminUserResponse])
async def list_users(
    _caller: User = Depends(_require_admin),
) -> list[AdminUserResponse]:
    all_users = await admin_service.list_users()
    return [_to_response(u) for u in all_users]


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: AdminCreateUserRequest,
    _caller: User = Depends(_require_admin),
) -> AdminUserResponse:
    if body.password != body.password_confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )
    if len(body.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password too short (min 6)",
        )

    user = await admin_service.create_user(body.username, body.password, body.role)
    return _to_response(user)


@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def set_password(
    user_id: str,
    body: AdminSetPasswordRequest,
    _caller: User = Depends(_require_admin),
) -> None:
    if body.password != body.password_confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )
    if len(body.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password too short (min 6)",
        )

    await admin_service.set_user_password(int(user_id), body.password)


@router.put("/{user_id}/role", status_code=status.HTTP_204_NO_CONTENT)
async def set_role(
    user_id: str,
    body: AdminSetRoleRequest,
    caller: User = Depends(_require_admin),
) -> None:
    await admin_service.set_user_role(int(user_id), body.role, caller)


@router.put("/{user_id}/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_user(
    user_id: str,
    caller: User = Depends(_require_admin),
) -> None:
    await admin_service.disable_user(int(user_id), caller)
