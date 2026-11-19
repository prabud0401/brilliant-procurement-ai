import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field


class PRLineCreate(BaseModel):
    product_id: uuid.UUID | None = None
    description: str
    qty: Decimal
    uom: str = "unit"
    est_unit_price: Decimal = Decimal("0.00")


class PRLineResponse(BaseModel):
    id: uuid.UUID
    pr_id: uuid.UUID
    product_id: uuid.UUID | None = None
    description: str
    qty: Decimal
    uom: str
    est_unit_price: Decimal

    model_config = ConfigDict(from_attributes=True)


class PRCreateRequest(BaseModel):
    title: str
    department_id: uuid.UUID | None = None
    lines: list[PRLineCreate] = Field(min_length=1)


class PRUpdateRequest(BaseModel):
    title: str | None = None
    department_id: uuid.UUID | None = None
    lines: list[PRLineCreate] | None = None


class PRResponse(BaseModel):
    id: uuid.UUID
    number: str
    requester_id: uuid.UUID
    department_id: uuid.UUID
    title: str
    status: str
    total_aed: Decimal
    currency: str
    rule_snapshot: dict[str, Any] | None = None
    submitted_at: datetime | None = None
    created_at: datetime
    lines: list[PRLineResponse] = Field(default_factory=list)
    current_approver_id: uuid.UUID | None = None
    current_approver: str | None = None

    model_config = ConfigDict(from_attributes=True)


class POLineResponse(BaseModel):
    id: uuid.UUID
    po_id: uuid.UUID
    line_no: int
    product_id: uuid.UUID | None = None
    description: str
    qty: Decimal
    uom: str
    unit_price: Decimal
    vat_rate: Decimal

    @computed_field  # type: ignore[prop-decorator]
    @property
    def line_total(self) -> Decimal:
        return self.qty * self.unit_price

    model_config = ConfigDict(from_attributes=True)


class POCreateRequest(BaseModel):
    comparison_id: uuid.UUID


class POResponse(BaseModel):
    id: uuid.UUID
    number: str
    comparison_id: uuid.UUID | None = None
    vendor_id: uuid.UUID
    department_id: uuid.UUID
    created_by: uuid.UUID
    status: str
    subtotal: Decimal
    vat: Decimal
    total: Decimal
    currency: str
    odoo_ref: str | None = None
    idempotency_key: str | None = None
    created_at: datetime
    lines: list[POLineResponse] = Field(default_factory=list)
    current_approver_id: uuid.UUID | None = None
    current_approver: str | None = None

    model_config = ConfigDict(from_attributes=True)


class POPushResponse(BaseModel):
    status: str
    odoo_ref: str
