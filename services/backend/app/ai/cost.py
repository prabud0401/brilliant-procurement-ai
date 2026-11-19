"""Token and cost estimation and daily budget enforcement."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ProblemException
from app.core.models import Extraction, Setting

# gpt-4o-mini pricing: $0.15 / 1M prompt tokens, $0.60 / 1M completion tokens, USD/AED = 3.6725
PRICE_PER_INPUT_TOKEN_AED = Decimal("0.0000005509")
PRICE_PER_OUTPUT_TOKEN_AED = Decimal("0.0000022035")


def calculate_cost_aed(tokens_in: int, tokens_out: int) -> Decimal:
    """Calculate estimated cost in AED for LLM tokens."""
    cost = (Decimal(tokens_in) * PRICE_PER_INPUT_TOKEN_AED) + (
        Decimal(tokens_out) * PRICE_PER_OUTPUT_TOKEN_AED
    )
    return cost.quantize(Decimal("0.0001"))


def get_daily_budget_aed(session: Session) -> Decimal:
    """Retrieve daily AI budget in AED from settings table or fallback to config."""
    db_setting = session.execute(
        select(Setting).where(Setting.key == "ai_daily_budget_aed")
    ).scalar_one_or_none()

    if db_setting and isinstance(db_setting.value, (int, float, str, Decimal)):
        try:
            return Decimal(str(db_setting.value))
        except Exception:
            pass
    elif db_setting and isinstance(db_setting.value, dict) and "value" in db_setting.value:
        try:
            return Decimal(str(db_setting.value["value"]))
        except Exception:
            pass

    return Decimal(str(settings.AI_DAILY_BUDGET_AED))


def get_today_spent_aed(session: Session) -> Decimal:
    """Calculate total spent on AI extractions today in UTC."""
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc)

    total_spent = session.execute(
        select(func.coalesce(func.sum(Extraction.est_cost), Decimal("0.0000"))).where(
            Extraction.created_at >= today_start
        )
    ).scalar_one()

    return Decimal(str(total_spent))


def check_daily_budget(session: Session) -> None:
    """Enforce daily AI budget. Raises ProblemException(429) if exceeded."""
    budget = get_daily_budget_aed(session)
    spent = get_today_spent_aed(session)

    if spent >= budget:
        detail_msg = (
            f"Daily AI processing budget of {budget:.2f} AED reached "
            f"(spent: {spent:.2f} AED). Processing temporarily paused."
        )
        raise ProblemException(
            status_code=429,
            code="AI_BUDGET_EXCEEDED",
            title="Daily AI Budget Exceeded",
            detail=detail_msg,
        )
