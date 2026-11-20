"""Unit tests for Q&A scorer (AIQ-06) per F03 scope."""

from __future__ import annotations

import pytest

from eval.metrics import score_qa_answer


@pytest.mark.unit
def test_qa_scorer_qa12_cases() -> None:
    # QA-12 expected "10 units"
    expected = "10 units"
    # Live model answer format that previously failed due to dropping tokens <= 2
    actual_correct = "PO-0061 ordered 10 ergonomic high-back mesh office chairs."
    assert score_qa_answer(expected, actual_correct) is True

    # Variations
    assert score_qa_answer(expected, "10 ergonomic chairs") is True
    assert score_qa_answer(expected, "Ordered 10.00 units") is True
    assert score_qa_answer(expected, "There are 10 items") is True

    # Wrong number must fail
    actual_wrong = "PO-0061 ordered 12 ergonomic high-back mesh office chairs."
    assert score_qa_answer(expected, actual_wrong) is False
    assert score_qa_answer(expected, "PO-0061 ordered 8 units") is False


@pytest.mark.unit
def test_qa_scorer_qa13_and_qa14_cases() -> None:
    # QA-13 expected "12 units"
    expected_13 = "12 units"
    assert (
        score_qa_answer(
            expected_13,
            "Oasis Facility Services invoiced 12 ergonomic chairs on INV-9041.",
        )
        is True
    )
    assert score_qa_answer(expected_13, "Invoiced 10 ergonomic chairs on INV-9041.") is False

    # QA-14 expected "10 units"
    expected_14 = "10 units"
    assert (
        score_qa_answer(
            expected_14,
            "According to delivery note DN-1090, 10 ergonomic chairs were received.",
        )
        is True
    )
    wrong_14 = "Delivery note DN-1090 shows 12 chairs were received."
    assert score_qa_answer(expected_14, wrong_14) is False


@pytest.mark.unit
def test_qa_scorer_currency_and_amounts() -> None:
    # QA-03 / QA-07: expected "AED 28,875.00"
    expected = "AED 28,875.00"

    assert score_qa_answer(expected, "The total amount is AED 28,875.00") is True
    assert score_qa_answer(expected, "Total amount: 28875.00 AED") is True
    assert score_qa_answer(expected, "Total is AED 28,875") is True
    assert score_qa_answer(expected, "The cost was 28875") is True

    # Wrong number must strictly fail
    assert score_qa_answer(expected, "The total amount is AED 29,820.00") is False
    assert score_qa_answer(expected, "Total is 31,185.00") is False


@pytest.mark.unit
def test_qa_scorer_multi_number_matching() -> None:
    # QA-15: "Over-billed by 2 units (invoiced 12 vs received 10)"
    expected = "Over-billed by 2 units (invoiced 12 vs received 10)"

    # All numbers (2, 12, 10) matched
    actual_correct = (
        "There is an over-billing of 2 units: 12 chairs invoiced on INV-9041 "
        "vs 10 received on DN-1090."
    )
    assert score_qa_answer(expected, actual_correct) is True

    # Main difference (2) matched
    actual_diff_only = "Invoice INV-9041 was over-billed by 2 chairs."
    assert score_qa_answer(expected, actual_diff_only) is True

    # Component numbers (12 vs 10) matched
    actual_components = (
        "Invoice INV-9041 invoiced 12 units vs 10 units received, an over-billing discrepancy."
    )
    assert score_qa_answer(expected, actual_components) is True

    # Wrong discrepancy number must fail
    actual_wrong_num = "Over-billed by 3 units (invoiced 12 vs received 9)"
    assert score_qa_answer(expected, actual_wrong_num) is False

    # Wrong component numbers must fail
    actual_wrong_components = "Invoiced 15 units vs 10 units received."
    assert score_qa_answer(expected, actual_wrong_components) is False


@pytest.mark.unit
def test_qa_scorer_text_questions() -> None:
    # QA-24: "Corniche Electrical Co."
    expected = "Corniche Electrical Co."
    assert (
        score_qa_answer(
            expected,
            "Corniche Electrical Co. provided quotation Q-3055.",
        )
        is True
    )
    assert (
        score_qa_answer(
            expected,
            "Falcon Office Supplies provided quotation Q-8821.",
        )
        is False
    )


@pytest.mark.unit
def test_qa_scorer_refusal() -> None:
    expected = "10 units"
    actual = "PO-0061 ordered 10 chairs."
    # If the answer was marked refused, it must score as False
    assert score_qa_answer(expected, actual, was_refused=True) is False
    assert score_qa_answer(expected, "", was_refused=False) is False
    assert score_qa_answer("", actual, was_refused=False) is False


@pytest.mark.unit
def test_qa_scorer_qa11_wording_variation() -> None:
    expected = "AED 16.00 per roll (+5% above PO price)"
    answer = (
        "The PO (PO-0050) unit price for Cat6 cable is AED 320.00 per roll. "
        "The invoice (INV-5510) unit price is AED 336.00 per roll. The unit price "
        "variance is AED 16.00 per roll, which represents a +5% increase from the PO price."
    )
    assert score_qa_answer(expected, answer) is True
    wrong = answer.replace("16.00", "18.00")
    assert score_qa_answer(expected, wrong) is False
