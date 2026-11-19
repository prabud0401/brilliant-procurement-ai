import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ComparisonCreateRequest(BaseModel):
    pr_id: uuid.UUID
    quote_document_ids: list[uuid.UUID] = Field(min_length=2)


class PairingUpdateItem(BaseModel):
    pr_line_id: uuid.UUID
    document_id: uuid.UUID
    extracted_line_id: uuid.UUID | None = None


class QuoteUpdateItem(BaseModel):
    included: bool
    include_reason: str | None = None


class WeightsUpdateRequest(BaseModel):
    cost: int = 60
    delivery: int = 20
    payment: int = 10
    completeness: int = 10


class DecisionRequest(BaseModel):
    vendor_id: uuid.UUID
    override_reason: str | None = None


class PairingResponse(BaseModel):
    id: uuid.UUID
    pr_line_id: uuid.UUID
    document_id: uuid.UUID
    extracted_line_id: uuid.UUID | None = None
    method: str

    model_config = ConfigDict(from_attributes=True)


class ComparisonQuoteResponse(BaseModel):
    document_id: uuid.UUID
    vendor_id: uuid.UUID | None = None
    vendor_name: str | None = None
    included: bool
    include_reason: str | None = None
    is_expired: bool = False
    currency: str = "AED"
    total_aed: Decimal = Decimal("0.00")
    lead_time_days: int | None = None
    payment_terms_days: int | None = None


class ComparisonResponse(BaseModel):
    id: uuid.UUID
    pr_id: uuid.UUID
    created_by: uuid.UUID
    status: str
    weights: dict[str, int]
    scores: dict[str, Any] | None = None
    recommended_vendor_id: uuid.UUID | None = None
    chosen_vendor_id: uuid.UUID | None = None
    override_reason: str | None = None
    explanation: str | None = None
    created_at: datetime
    quotes: list[ComparisonQuoteResponse] = Field(default_factory=list)
    pairings: list[PairingResponse] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class RecommendationResponse(BaseModel):
    scores: dict[str, Any]
    recommended_vendor_id: uuid.UUID
    winner_name: str
    is_close: bool
    margin: float
    explanation: str
