"""Admin observability and business metrics schemas per design 9.1 and US-19."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FieldCorrectionRate(BaseModel):
    field_name: str
    total_count: int
    corrected_count: int
    correction_rate: float


class AITodayMetrics(BaseModel):
    calls_today: int
    tokens_today: int
    tokens_in_today: int
    tokens_out_today: int
    estimated_cost_aed: float
    daily_budget_aed: float
    budget_utilization_pct: float


class AdminMetricsResponse(BaseModel):
    documents_processed: int
    total_fields: int
    fields_needing_review_count: int
    share_of_fields_needing_review: float
    correction_rate_per_field: list[FieldCorrectionRate] = Field(default_factory=list)
    match_exception_rate: float
    total_matches: int
    exception_matches: int
    approval_cycle_time_seconds: float | None
    approval_cycle_time_hours: float | None
    ai_today: AITodayMetrics
    qa_refusal_rate: float
    qa_total_questions: int
    qa_refused_questions: int
