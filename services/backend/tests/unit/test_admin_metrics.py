"""Unit tests for admin metrics computation logic and schema per design 9.1."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.metrics.schemas import (
    AdminMetricsResponse,
    AITodayMetrics,
    DepartmentSpendMetric,
    FieldCorrectionRate,
)
from app.metrics.service import compute_admin_metrics


@pytest.mark.unit
def test_admin_metrics_schema_validation() -> None:
    ai = AITodayMetrics(
        calls_today=15,
        tokens_today=25000,
        tokens_in_today=20000,
        tokens_out_today=5000,
        estimated_cost_aed=0.0350,
        daily_budget_aed=50.0,
        budget_utilization_pct=0.07,
    )
    rates = [
        FieldCorrectionRate(
            field_name="total_amount",
            total_count=10,
            corrected_count=2,
            correction_rate=0.20,
        ),
        FieldCorrectionRate(
            field_name="vendor_name",
            total_count=10,
            corrected_count=0,
            correction_rate=0.0,
        ),
    ]
    spend = [
        DepartmentSpendMetric(
            department_id="00000000-0000-0000-0000-000000000001",
            department_name="Facilities",
            purchase_requests_count=5,
            purchase_requests_total_aed=12500.00,
            purchase_orders_count=3,
            purchase_orders_total_aed=10000.00,
            pending_approvals_count=1,
        )
    ]
    resp = AdminMetricsResponse(
        documents_processed=12,
        total_fields=120,
        fields_needing_review_count=18,
        share_of_fields_needing_review=0.15,
        correction_rate_per_field=rates,
        match_exception_rate=0.08,
        total_matches=25,
        exception_matches=2,
        approval_cycle_time_seconds=3600.0,
        approval_cycle_time_hours=1.0,
        ai_today=ai,
        qa_refusal_rate=0.10,
        qa_total_questions=20,
        qa_refused_questions=2,
        spend_by_department=spend,
    )

    data = resp.model_dump()
    assert data["documents_processed"] == 12
    assert data["share_of_fields_needing_review"] == 0.15
    assert len(data["correction_rate_per_field"]) == 2
    assert data["match_exception_rate"] == 0.08
    assert data["ai_today"]["estimated_cost_aed"] == 0.0350
    assert data["qa_refusal_rate"] == 0.10
    assert len(data["spend_by_department"]) == 1
    assert data["spend_by_department"][0]["department_name"] == "Facilities"
    assert data["spend_by_department"][0]["purchase_requests_count"] == 5


@pytest.mark.unit
def test_compute_admin_metrics_empty_db() -> None:
    # Verify compute_admin_metrics does not crash on empty database tables
    mock_session = MagicMock()
    # Mock query executions returning 0 or empty lists
    mock_session.execute.return_value.scalar_one.return_value = 0
    mock_session.execute.return_value.all.return_value = []
    mock_session.execute.return_value.first.return_value = None

    metrics = compute_admin_metrics(mock_session)
    assert isinstance(metrics, AdminMetricsResponse)
    assert metrics.documents_processed == 0
    assert metrics.share_of_fields_needing_review == 0.0
    assert metrics.match_exception_rate == 0.0
    assert metrics.ai_today.calls_today == 0
    assert metrics.qa_refusal_rate == 0.0
    assert metrics.spend_by_department == []


@pytest.mark.unit
def test_compute_admin_metrics_spend_by_department_zero_rows() -> None:
    import uuid

    from app.core.models import Department

    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one.return_value = 0
    mock_session.execute.return_value.first.return_value = None

    dept_it = Department(id=uuid.uuid4(), name="IT")
    dept_fin = Department(id=uuid.uuid4(), name="Finance")

    # When querying departments, return 2 departments; for all other queries, return empty list
    def mock_execute(stmt: object) -> MagicMock:
        mock_res = MagicMock()
        mock_res.scalar_one.return_value = 0
        mock_res.first.return_value = None
        mock_res.all.return_value = []
        mock_res.scalars.return_value.all.return_value = [dept_fin, dept_it]
        return mock_res

    mock_session.execute.side_effect = mock_execute

    metrics = compute_admin_metrics(mock_session)
    assert len(metrics.spend_by_department) == 2
    for d in metrics.spend_by_department:
        assert d.purchase_requests_count == 0
        assert d.purchase_requests_total_aed == 0.0
        assert d.purchase_orders_count == 0
        assert d.purchase_orders_total_aed == 0.0
        assert d.pending_approvals_count == 0
