"""Metrics calculation service aggregating operational and observability KPIs from Postgres."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.ai.cost import calculate_cost_aed, get_daily_budget_aed
from app.core.models import (
    ApprovalStep,
    Document,
    ExtractedField,
    Extraction,
    Match,
    QALog,
)
from app.metrics.schemas import (
    AdminMetricsResponse,
    AITodayMetrics,
    FieldCorrectionRate,
)


def compute_admin_metrics(session: Session) -> AdminMetricsResponse:
    """Calculate all business and AI metrics for the Admin dashboard from Postgres."""
    # 1. Documents Processed
    docs_count = (
        session.execute(
            select(func.count(Document.id)).where(
                Document.status.in_(["needs_review", "confirmed", "failed"])
            )
        ).scalar_one()
        or 0
    )

    if docs_count == 0:
        docs_count = session.execute(select(func.count(Document.id))).scalar_one() or 0

    # 2. Share of Fields Needing Review
    total_fields = session.execute(select(func.count(ExtractedField.id))).scalar_one() or 0
    needing_review_count = (
        session.execute(
            select(func.count(ExtractedField.id)).where(
                ExtractedField.status.in_(["needs_review", "validation_failed"])
            )
        ).scalar_one()
        or 0
    )

    share_needing_review = (
        round(float(needing_review_count) / float(total_fields), 4) if total_fields > 0 else 0.0
    )

    # 3. Correction Rate per Field
    field_rows = session.execute(
        select(
            ExtractedField.name,
            func.count(ExtractedField.id).label("total"),
            func.count(case((ExtractedField.status == "corrected", 1), else_=None)).label(
                "corrected"
            ),
        ).group_by(ExtractedField.name)
    ).all()

    correction_rates: list[FieldCorrectionRate] = []
    for r in field_rows:
        f_name, f_total, f_corrected = r[0], r[1] or 0, r[2] or 0
        rate = round(float(f_corrected) / float(f_total), 4) if f_total > 0 else 0.0
        correction_rates.append(
            FieldCorrectionRate(
                field_name=f_name,
                total_count=f_total,
                corrected_count=f_corrected,
                correction_rate=rate,
            )
        )
    correction_rates.sort(key=lambda x: x.field_name)

    # 4. Three-Way Match Exception Rate
    total_matches = session.execute(select(func.count(Match.id))).scalar_one() or 0
    exception_matches = (
        session.execute(
            select(func.count(Match.id)).where(Match.overall_status == "exception")
        ).scalar_one()
        or 0
    )

    match_exception_rate = (
        round(float(exception_matches) / float(total_matches), 4) if total_matches > 0 else 0.0
    )

    # 5. Approval Cycle Time
    approval_steps = session.execute(
        select(ApprovalStep.created_at, ApprovalStep.decided_at).where(
            ApprovalStep.decided_at.isnot(None)
        )
    ).all()

    avg_cycle_seconds: float | None = None
    avg_cycle_hours: float | None = None
    if approval_steps:
        durations = [
            (step[1] - step[0]).total_seconds() for step in approval_steps if step[0] and step[1]
        ]
        if durations:
            avg_cycle_seconds = round(sum(durations) / len(durations), 1)
            avg_cycle_hours = round(avg_cycle_seconds / 3600.0, 2)

    # 6. AI Calls / Tokens / Cost Today vs Daily Budget
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc)

    ext_stats = session.execute(
        select(
            func.count(Extraction.id),
            func.coalesce(func.sum(Extraction.tokens_in), 0),
            func.coalesce(func.sum(Extraction.tokens_out), 0),
            func.coalesce(func.sum(Extraction.est_cost), Decimal("0.0000")),
        ).where(Extraction.created_at >= today_start)
    ).first()

    ext_calls = int(ext_stats[0] or 0) if ext_stats else 0
    ext_tokens_in = int(ext_stats[1] or 0) if ext_stats else 0
    ext_tokens_out = int(ext_stats[2] or 0) if ext_stats else 0
    ext_cost = (
        Decimal(str(ext_stats[3]))
        if (ext_stats and ext_stats[3] is not None)
        else Decimal("0.0000")
    )

    qa_today_stats = session.execute(
        select(
            func.count(QALog.id),
            func.coalesce(func.sum(QALog.tokens_in), 0),
            func.coalesce(func.sum(QALog.tokens_out), 0),
        ).where(QALog.created_at >= today_start)
    ).first()

    qa_today_calls = int(qa_today_stats[0] or 0) if qa_today_stats else 0
    qa_today_tin = int(qa_today_stats[1] or 0) if qa_today_stats else 0
    qa_today_tout = int(qa_today_stats[2] or 0) if qa_today_stats else 0
    qa_cost = calculate_cost_aed(qa_today_tin, qa_today_tout)

    total_ai_calls_today = ext_calls + qa_today_calls
    total_tokens_in_today = ext_tokens_in + qa_today_tin
    total_tokens_out_today = ext_tokens_out + qa_today_tout
    total_tokens_today = total_tokens_in_today + total_tokens_out_today

    total_spent_today = float(ext_cost + qa_cost)
    daily_budget = float(get_daily_budget_aed(session))
    budget_pct = round((total_spent_today / daily_budget) * 100.0, 2) if daily_budget > 0 else 0.0

    ai_today_metrics = AITodayMetrics(
        calls_today=total_ai_calls_today,
        tokens_today=total_tokens_today,
        tokens_in_today=total_tokens_in_today,
        tokens_out_today=total_tokens_out_today,
        estimated_cost_aed=round(total_spent_today, 4),
        daily_budget_aed=daily_budget,
        budget_utilization_pct=budget_pct,
    )

    # 7. Q&A Refusal Rate
    total_qa = session.execute(select(func.count(QALog.id))).scalar_one() or 0
    refused_qa = (
        session.execute(select(func.count(QALog.id)).where(QALog.refused.is_(True))).scalar_one()
        or 0
    )

    qa_refusal_rate = round(float(refused_qa) / float(total_qa), 4) if total_qa > 0 else 0.0

    return AdminMetricsResponse(
        documents_processed=docs_count,
        total_fields=total_fields,
        fields_needing_review_count=needing_review_count,
        share_of_fields_needing_review=share_needing_review,
        correction_rate_per_field=correction_rates,
        match_exception_rate=match_exception_rate,
        total_matches=total_matches,
        exception_matches=exception_matches,
        approval_cycle_time_seconds=avg_cycle_seconds,
        approval_cycle_time_hours=avg_cycle_hours,
        ai_today=ai_today_metrics,
        qa_refusal_rate=qa_refusal_rate,
        qa_total_questions=total_qa,
        qa_refused_questions=refused_qa,
    )
