"""Unit tests for AI cost metering, daily budget enforcement, and response caching."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.ai.cache import clear_cache, get_cached_extraction, store_cached_extraction
from app.ai.cost import calculate_cost_aed, check_daily_budget
from app.ai.schemas import ExtractionResult
from app.core.errors import ProblemException


@pytest.mark.unit
def test_calculate_cost_aed() -> None:
    # 1000 input tokens, 200 output tokens
    cost = calculate_cost_aed(1000, 200)
    assert isinstance(cost, Decimal)
    assert cost > Decimal("0.0000")


@pytest.mark.unit
def test_daily_budget_check_within_budget() -> None:
    session = MagicMock()
    # Mock budget = 7.0 AED, spent = 2.0 AED
    session.execute.return_value.scalar_one_or_none.return_value = None
    session.execute.return_value.scalar_one.return_value = Decimal("2.0000")

    # Should not raise
    check_daily_budget(session)


@pytest.mark.unit
def test_daily_budget_check_exceeded() -> None:
    session = MagicMock()
    # Mock budget = 50.0 AED, spent = 55.0 AED
    session.execute.return_value.scalar_one_or_none.return_value = None
    session.execute.return_value.scalar_one.return_value = Decimal("55.0000")

    with pytest.raises(ProblemException) as exc_info:
        check_daily_budget(session)
    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "AI_BUDGET_EXCEEDED"


@pytest.mark.unit
def test_response_cache_hit_and_miss() -> None:
    clear_cache()
    sha = "test-hash-12345"
    prompt_ver = "prompts/extract_v1.md"

    assert get_cached_extraction(sha, prompt_ver) is None

    result = ExtractionResult(doc_type="quote", header={}, lines=[])
    meta = {"tokens_in": 100, "tokens_out": 50, "model": "mock"}

    store_cached_extraction(sha, prompt_ver, result, meta)
    cached = get_cached_extraction(sha, prompt_ver)
    assert cached is not None
    cached_res, cached_meta = cached
    assert cached_res.doc_type == "quote"
    assert cached_meta["tokens_in"] == 100
