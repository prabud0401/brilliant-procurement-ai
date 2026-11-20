"""Token and cost estimation and daily budget enforcement."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ProblemException
from app.core.models import Extraction, Setting

USD_TO_AED = Decimal("3.6725")

# Price table in USD per 1M tokens (prompt / completion)
MODEL_PRICES_USD_PER_1M: dict[str, dict[str, Decimal]] = {
    "gpt-5-mini": {"input": Decimal("0.25"), "output": Decimal("2.00")},
    "gpt-5.4-mini": {"input": Decimal("0.75"), "output": Decimal("4.50")},
    "gpt-4o-mini": {"input": Decimal("0.15"), "output": Decimal("0.60")},
    "text-embedding-3-small": {"input": Decimal("0.02"), "output": Decimal("0.00")},
}

# Conservative rates for unknown models: highest listed rates in the table
UNKNOWN_MODEL_INPUT_PRICE_USD_PER_1M = max(p["input"] for p in MODEL_PRICES_USD_PER_1M.values())
UNKNOWN_MODEL_OUTPUT_PRICE_USD_PER_1M = max(p["output"] for p in MODEL_PRICES_USD_PER_1M.values())


def get_model_token_rates_usd(model: str | None = None) -> tuple[Decimal, Decimal]:
    """Return (input_rate_usd, output_rate_usd) per token for model.

    If model is unknown, falls back to the most expensive listed rate (conservative).
    """
    model_key = (model or settings.AZURE_OPENAI_DEPLOYMENT or "").strip().lower()

    rates: dict[str, Decimal] | None = None
    if model_key in MODEL_PRICES_USD_PER_1M:
        rates = MODEL_PRICES_USD_PER_1M[model_key]
    else:
        # Check substring match (e.g. deployment aliases)
        for key, price_dict in MODEL_PRICES_USD_PER_1M.items():
            if key in model_key:
                rates = price_dict
                break

    if rates is None:
        rates = {
            "input": UNKNOWN_MODEL_INPUT_PRICE_USD_PER_1M,
            "output": UNKNOWN_MODEL_OUTPUT_PRICE_USD_PER_1M,
        }

    rate_in_usd = rates["input"] / Decimal("1000000")
    rate_out_usd = rates["output"] / Decimal("1000000")
    return rate_in_usd, rate_out_usd


def calculate_cost_usd(tokens_in: int, tokens_out: int, model: str | None = None) -> Decimal:
    """Calculate estimated cost in USD for LLM tokens."""
    rate_in_usd, rate_out_usd = get_model_token_rates_usd(model)
    return (Decimal(tokens_in) * rate_in_usd) + (Decimal(tokens_out) * rate_out_usd)


def calculate_cost_aed(tokens_in: int, tokens_out: int, model: str | None = None) -> Decimal:
    """Calculate estimated cost in AED for LLM tokens."""
    cost_usd = calculate_cost_usd(tokens_in, tokens_out, model)
    cost_aed = cost_usd * USD_TO_AED
    return cost_aed.quantize(Decimal("0.0001"))


# Backward-compatibility constants
PRICE_PER_INPUT_TOKEN_AED = (
    MODEL_PRICES_USD_PER_1M["gpt-4o-mini"]["input"] / Decimal("1000000") * USD_TO_AED
)
PRICE_PER_OUTPUT_TOKEN_AED = (
    MODEL_PRICES_USD_PER_1M["gpt-4o-mini"]["output"] / Decimal("1000000") * USD_TO_AED
)


def record_ai_call_metrics(
    task: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    model: str | None = None,
    prompt_version: str | None = None,
    latency_ms: int | float | None = None,
    refusal_flag: bool = False,
    injection_flag: bool = False,
) -> Decimal:
    """Calculate cost and emit an AI metric event per NFR-OBS-02."""
    cost = calculate_cost_aed(tokens_in, tokens_out, model=model)
    try:
        from app.observability.ai_events import emit_ai_metric_event

        emit_ai_metric_event(
            task=task,
            model=model,
            prompt_version=prompt_version,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            estimated_cost=cost,
            refusal_flag=refusal_flag,
            injection_flag=injection_flag,
        )
    except Exception:
        pass
    return cost


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
