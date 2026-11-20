import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.admin.schemas import (
    AdminDepartmentResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    IntegrationStatusItem,
    RetentionSettingsResponse,
    RetentionSettingsUpdateRequest,
    SettingHistoryItem,
)
from app.admin.service import (
    get_retention_settings,
    get_setting_history,
    get_user,
    list_departments,
    list_integrations,
    list_users,
    update_retention_settings,
    update_user,
)
from app.core.database import get_db
from app.core.policy import Principal, require

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserResponse])
def get_all_users(
    principal: Principal = Depends(require("admin.manage")),
    db: Session = Depends(get_db),
) -> list[AdminUserResponse]:
    return list_users(db)


@router.get("/users/{id}", response_model=AdminUserResponse)
def get_user_by_id(
    id: uuid.UUID,
    principal: Principal = Depends(require("admin.manage")),
    db: Session = Depends(get_db),
) -> AdminUserResponse:
    return get_user(db, id)


@router.patch("/users/{id}", response_model=AdminUserResponse)
def update_user_by_id(
    id: uuid.UUID,
    body: AdminUserUpdateRequest,
    principal: Principal = Depends(require("admin.manage")),
    db: Session = Depends(get_db),
) -> AdminUserResponse:
    return update_user(db, id, body, principal)


@router.get("/departments", response_model=list[AdminDepartmentResponse])
def get_departments(
    principal: Principal = Depends(require("admin.manage")),
    db: Session = Depends(get_db),
) -> list[AdminDepartmentResponse]:
    return list_departments(db)


@router.get("/integrations", response_model=list[IntegrationStatusItem])
def get_integrations(
    principal: Principal = Depends(require("admin.manage")),
) -> list[IntegrationStatusItem]:
    return list_integrations()


@router.get("/settings/{key}/history", response_model=list[SettingHistoryItem])
def get_setting_version_history(
    key: str,
    principal: Principal = Depends(require("admin.manage")),
    db: Session = Depends(get_db),
) -> list[SettingHistoryItem]:
    return get_setting_history(db, key)


@router.get("/retention", response_model=RetentionSettingsResponse)
def get_retention(
    principal: Principal = Depends(require("admin.manage")),
    db: Session = Depends(get_db),
) -> RetentionSettingsResponse:
    return get_retention_settings(db)


@router.put("/retention", response_model=RetentionSettingsResponse)
def put_retention(
    body: RetentionSettingsUpdateRequest,
    principal: Principal = Depends(require("admin.manage")),
    db: Session = Depends(get_db),
) -> RetentionSettingsResponse:
    return update_retention_settings(db, body, principal)
