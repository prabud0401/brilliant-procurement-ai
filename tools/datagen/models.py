"""Data models for document scenarios and ground truth."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

DocType = Literal["quotation", "purchase_order", "delivery_note", "invoice", "purchase_request"]


class DocumentLine(BaseModel):
    """Line item in a document scenario."""

    line_no: int
    item_code: str
    description: str
    qty: Decimal
    uom: str
    unit_price: Decimal
    discount: Decimal = Field(default=Decimal("0.00"))
    vat_rate: Decimal = Field(default=Decimal("5.00"))
    line_total: Decimal


class GroundTruth(BaseModel):
    """Ground truth data corresponding to a synthetic document."""

    doc_id: str
    scenario_id: str
    doc_type: DocType
    vendor_name: str
    vendor_trn: str
    document_number: str
    document_date: str  # YYYY-MM-DD
    currency: str = "AED"
    po_number: str | None = None
    pr_number: str | None = None
    payment_terms: str | None = None
    due_date: str | None = None
    lead_time_days: int | None = None
    lines: list[DocumentLine] = Field(default_factory=list)
    subtotal: Decimal
    vat: Decimal
    total: Decimal
    injection_expected: bool = False
    injection_snippet: str | None = None
    injection_type: str | None = None  # hidden_text, prompt_leak, etc.
    layout_name: str = "modern_tech"
    is_scanned: bool = False
    notes: str = ""


class ScenarioDocSpec(BaseModel):
    """Specification used by generator to render a document and emit ground truth."""

    doc_id: str
    scenario_id: str
    doc_type: DocType
    vendor_name: str
    vendor_trn: str
    vendor_address: str = ""
    vendor_email: str = ""
    vendor_phone: str = ""
    document_number: str
    document_date: str
    currency: str = "AED"
    customer_name: str = "Demo Holdings LLC"
    customer_address: str = "Al Maryah Island, Abu Dhabi, UAE"
    po_number: str | None = None
    pr_number: str | None = None
    payment_terms: str | None = None
    due_date: str | None = None
    lead_time_days: int | None = None
    lines: list[DocumentLine] = Field(default_factory=list)
    subtotal: Decimal
    vat: Decimal
    total: Decimal
    # Layout choices: modern_tech, classic_corporate, minimalist_slate, landscape_industrial
    layout_name: str = "modern_tech"
    is_scanned: bool = False
    injection_expected: bool = False
    injection_snippet: str | None = None
    injection_type: str | None = None
    hidden_text: str | None = None
    notes: str = ""
