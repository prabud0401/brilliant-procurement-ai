import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InboxItemResponse(BaseModel):
    step_id: uuid.UUID
    subject_type: str
    subject_id: uuid.UUID
    subject_number: str
    title: str
    total_aed: Decimal
    requester_id: uuid.UUID
    requester_name: str
    department_id: uuid.UUID
    department_name: str | None = None
    tier: int
    sequence: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(description="'approve' or 'reject'")
    comment: str | None = Field(default=None, description="Mandatory when rejecting")


class ApprovalDecisionResponse(BaseModel):
    step_id: uuid.UUID
    status: str
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    comment: str | None
    subject_status: str

    model_config = ConfigDict(from_attributes=True)


class EarlierDecision(BaseModel):
    step_id: uuid.UUID
    sequence: int
    tier: int
    assigned_to: uuid.UUID | None
    decided_by: uuid.UUID | None
    decided_by_name: str | None
    status: str
    comment: str | None
    decided_at: datetime | None


class ApprovalBundleResponse(BaseModel):
    step_id: uuid.UUID
    subject_type: str
    subject_id: uuid.UUID
    sequence: int
    tier: int
    step_status: str
    assigned_to: uuid.UUID | None

    subject: dict[str, Any]
    earlier_decisions: list[EarlierDecision] = Field(default_factory=list)
    comparison: dict[str, Any] | None = None
    match: dict[str, Any] | None = None
