import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MatchCreateRequest(BaseModel):
    invoice_document_id: uuid.UUID


class MatchLineResponse(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    po_line_id: uuid.UUID | None = None
    invoice_line_id: uuid.UUID | None = None
    ordered_qty: Decimal | None = None
    received_qty: Decimal | None = None
    invoiced_qty: Decimal | None = None
    po_unit_price: Decimal | None = None
    inv_unit_price: Decimal | None = None
    variance_aed: Decimal
    status: str
    reason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MatchExceptionResponse(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    match_line_id: uuid.UUID | None = None
    kind: str
    reason: str
    amount_impact_aed: Decimal
    status: str
    assigned_to: uuid.UUID | None = None
    resolved_by: uuid.UUID | None = None
    resolution: str | None = None
    resolution_reason: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MatchResponse(BaseModel):
    id: uuid.UUID
    invoice_document_id: uuid.UUID
    po_id: uuid.UUID
    run_by: uuid.UUID
    overall_status: str
    tolerance_snapshot: dict[str, Any] | None = None
    created_at: datetime
    lines: list[MatchLineResponse] = Field(default_factory=list)
    exceptions: list[MatchExceptionResponse] = Field(default_factory=list)
    invoice_document_number: str | None = None
    vendor_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ExceptionResolveRequest(BaseModel):
    action: str = Field(description="'accept', 'escalate', 'reject', 'reject_credit_note', 'wait'")
    reason: str = Field(min_length=3, description="Mandatory reason for the resolution action")
