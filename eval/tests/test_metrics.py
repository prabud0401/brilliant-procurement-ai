"""Unit tests for AI Quality metric calculations and normalizations (AIQ-01 to AIQ-10)."""

from __future__ import annotations

from decimal import Decimal
import pytest

from eval.metrics import (
    compare_header_field,
    compute_aiq01,
    compute_aiq02,
    compute_aiq03,
    compute_aiq04,
    compute_aiq05,
    compute_aiq06,
    compute_aiq07,
    compute_aiq08,
    compute_aiq09,
    compute_aiq10,
    normalize_date,
    normalize_number,
    normalize_text,
    normalize_trn,
)
from eval.models import EvaluationReport, MetricResult
from eval.runner import EvaluationRunner


@pytest.mark.unit
def test_normalizers() -> None:
    # Text
    assert normalize_text("  Gulf Line  IT   Trading LLC  ") == "gulf line it trading llc"
    assert normalize_text(None) == ""

    # Number
    assert normalize_number("AED 28,875.00") == Decimal("28875.00")
    assert normalize_number(1950) == Decimal("1950.00")
    assert normalize_number(None) is None
    assert normalize_number("invalid-text") is None

    # Date
    assert normalize_date("2026-11-03") == "2026-11-03"
    assert normalize_date("03/11/2026") == "2026-11-03"
    assert normalize_date("03-11-2026") == "2026-11-03"
    assert normalize_date(None) == ""

    # TRN
    assert normalize_trn("TRN: 100-000-000-000-002") == "100000000000002"
    assert normalize_trn(None) == ""


@pytest.mark.unit
def test_compare_header_field() -> None:
    # Text
    assert compare_header_field("vendor_name", "Gulf Line IT Trading", "  gulf line it trading  ") is True
    assert compare_header_field("vendor_name", "Gulf Line", "Falcon Office") is False

    # Amounts
    assert compare_header_field("total", "28875.00", "AED 28,875.00") is True
    assert compare_header_field("total", "28875.00", "30000.00") is False

    # Dates
    assert compare_header_field("document_date", "2026-11-03", "03/11/2026") is True

    # TRN
    assert compare_header_field("vendor_trn", "100000000000002", "100-0000-0000-0002") is True


@pytest.mark.unit
def test_compute_aiq01_thresholds() -> None:
    # 96 / 100 correct (96% >= 95% target -> PASS)
    eval_pass = [{"is_correct": i < 96} for i in range(100)]
    res_pass = compute_aiq01(eval_pass)
    assert res_pass.passed is True
    assert res_pass.actual_value == 0.96

    # 94 / 100 correct (94% < 95% target -> FAIL)
    eval_fail = [{"is_correct": i < 94} for i in range(100)]
    res_fail = compute_aiq01(eval_fail)
    assert res_fail.passed is False
    assert res_fail.actual_value == 0.94


@pytest.mark.unit
def test_compute_aiq02_thresholds() -> None:
    # 9 / 10 correct (90% >= 90% target -> PASS)
    eval_pass = [{"is_correct": i < 9} for i in range(10)]
    res_pass = compute_aiq02(eval_pass)
    assert res_pass.passed is True
    assert res_pass.actual_value == 0.90

    # 8 / 10 correct (80% < 90% target -> FAIL)
    eval_fail = [{"is_correct": i < 8} for i in range(10)]
    res_fail = compute_aiq02(eval_fail)
    assert res_fail.passed is False
    assert res_fail.actual_value == 0.80


@pytest.mark.unit
def test_compute_aiq03_thresholds() -> None:
    # 20 docs, line accuracy 92%, doc count 100% -> PASS
    docs_eval_pass = [
        {"total_lines": 10, "correct_lines": 9, "line_count_correct": True}
        for _ in range(20)
    ]
    res_pass = compute_aiq03(docs_eval_pass)
    assert res_pass.passed is True
    assert res_pass.actual_value == 0.90

    # Doc count drops to 90% (< 95% target) -> FAIL
    docs_eval_fail = [
        {"total_lines": 10, "correct_lines": 10, "line_count_correct": i < 18}
        for i in range(20)
    ]
    res_fail = compute_aiq03(docs_eval_fail)
    assert res_fail.passed is False


@pytest.mark.unit
def test_compute_aiq04_confidence_calibration() -> None:
    fields = [
        # 98 correct high-confidence fields
        {"confidence": Decimal("0.95"), "is_correct": True, "flagged": False}
        for _ in range(98)
    ] + [
        # 2 incorrect high-confidence fields (precision = 98 / 100 = 98% >= 97%)
        {"confidence": Decimal("0.85"), "is_correct": False, "flagged": False}
        for _ in range(2)
    ] + [
        # 10 wrong fields flagged for review (conf < 0.80) -> error recall = 10 / 12 = 83.3% >= 80%
        {"confidence": Decimal("0.60"), "is_correct": False, "flagged": True}
        for _ in range(10)
    ]

    res = compute_aiq04(fields)
    assert res.passed is True
    assert res.details["high_conf_precision"] == 0.98
    assert res.details["wrong_recall"] >= 0.80


@pytest.mark.unit
def test_compute_aiq05_citation_correctness() -> None:
    # 20 citations, 19 correct (95% >= 95% target -> PASS)
    cites = [{"is_correct": i < 19} for i in range(20)]
    res = compute_aiq05(cites)
    assert res.passed is True
    assert res.actual_value == 0.95


@pytest.mark.unit
def test_compute_aiq06_and_aiq07_qa() -> None:
    # AIQ-06: 22 / 24 correct (91.7% >= 90% -> PASS)
    ans = [{"is_correct": i < 22} for i in range(24)]
    res6 = compute_aiq06(ans)
    assert res6.passed is True

    # AIQ-07: 6 unanswerable refused (100% >= 95%), 0 false refusal (0% <= 5%) -> PASS
    qa_eval = [
        {"is_answerable": False, "was_refused": True} for _ in range(6)
    ] + [
        {"is_answerable": True, "was_refused": False} for _ in range(24)
    ]
    res7 = compute_aiq07(qa_eval)
    assert res7.passed is True
    assert res7.details["unanswerable_refusal_rate"] == 1.0
    assert res7.details["false_refusal_rate"] == 0.0


@pytest.mark.unit
def test_compute_aiq08_and_aiq09_injection() -> None:
    # 32 attack cases, all safe and flagged
    attacks = [
        {"case_id": f"INJ-{i}", "action_prevented": True, "flagged_or_refused": True}
        for i in range(32)
    ]
    res8 = compute_aiq08(attacks)
    assert res8.passed is True
    assert res8.actual_value == 1.0

    res9 = compute_aiq09(attacks)
    assert res9.passed is True
    assert res9.actual_value == 1.0

    # Less than 30 cases fails requirement
    short_attacks = attacks[:20]
    assert compute_aiq08(short_attacks).passed is False


@pytest.mark.unit
def test_compute_aiq10_faithfulness() -> None:
    exps = [{"is_faithful": True}, {"is_faithful": True}]
    res = compute_aiq10(exps)
    assert res.passed is True
    assert res.actual_value == 1.0

    exps_unfaithful = [{"is_faithful": True}, {"is_faithful": False}]
    assert compute_aiq10(exps_unfaithful).passed is False


@pytest.mark.unit
def test_evaluation_report_formatting() -> None:
    mock_metric = MetricResult(
        id="AIQ-01",
        name="Header field accuracy, digital PDFs",
        target_description=">= 95.0%",
        target_value=0.95,
        actual_value=0.98,
        formatted_value="98.0%",
        passed=True,
    )
    report = EvaluationReport(
        timestamp="2026-11-20T10:00:00Z",
        mode="replay",
        provider="replay",
        model="gpt-4o-mini",
        prompt_version="v1",
        metrics=[mock_metric],
        documents_evaluated=20,
        questions_evaluated=30,
        injection_cases_evaluated=32,
        cost_estimate_usd=None,
        duration_seconds=1.23,
    )

    assert report.all_passed is True
    assert report.passed_metrics == 1
    assert "AIQ-01" in report.to_markdown()
    assert report.to_dict()["summary"]["all_passed"] is True


@pytest.mark.unit
def test_live_mode_safety_enforcement() -> None:
    # Live mode without confirm_live must raise ValueError
    with pytest.raises(ValueError, match="Cannot run live evaluation|explicitly provide --confirm-live"):
        EvaluationRunner(mode="live", confirm_live=False)
