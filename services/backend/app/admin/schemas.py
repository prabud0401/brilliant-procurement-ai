import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    roles: list[str]
    department_id: uuid.UUID | None = None
    department_name: str | None = None
    approval_limit_aed: Decimal
    active: bool = True
    is_demo: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminUserUpdateRequest(BaseModel):
    roles: list[str] | None = None
    approval_limit_aed: Decimal | None = None
    department_id: uuid.UUID | None = None
    active: bool | None = None
    reason: str | None = Field(
        default=None,
        description="Mandatory reason when granting business roles to admin or self-granting",
    )


class AdminDepartmentResponse(BaseModel):
    id: uuid.UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class IntegrationStatusItem(BaseModel):
    adapter: str
    name: str
    mode: str
    label: str


class SettingHistoryItem(BaseModel):
    id: int
    occurred_at: datetime
    actor_id: uuid.UUID | None = None
    actor_name: str | None = None
    action: str
    version: int | None = None
    value: Any = None
    reason: str | None = None


class RetentionSettingsResponse(BaseModel):
    documents_retention_days: int
    audit_retention_days: int


class RetentionSettingsUpdateRequest(BaseModel):
    documents_retention_days: int | None = Field(default=None, ge=1)
    audit_retention_days: int | None = Field(default=None, ge=1)
