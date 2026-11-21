import uuid
from decimal import Decimal

import pytest

from app.comparison.explanation import TemplateExplanationWriter
from app.comparison.scoring import calculate_scores
from app.comparison.service import parse_lead_time


@pytest.mark.unit
def test_comparison_scoring_deterministic_formula() -> None:
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()

    # Vendor 1: Cheaper (10,000 AED), longer lead time (14 days), 30 days credit, 100% complete
    # Vendor 2: Expensive (12,500 AED), faster lead time (7 days), 60 days credit, 100% complete
    quotes_data = [
        {
            "vendor_id": v1_id,
            "vendor_name": "Vendor 1",
            "total_cost": Decimal("10000.00"),
            "lead_time_days": 14,
            "payment_terms_days": 30,
            "items_quoted": 5,
            "total_items_requested": 5,
        },
        {
            "vendor_id": v2_id,
            "vendor_name": "Vendor 2",
            "total_cost": Decimal("12500.00"),
            "lead_time_days": 7,
            "payment_terms_days": 60,
            "items_quoted": 5,
            "total_items_requested": 5,
        },
    ]

    weights = {"cost": 60, "delivery": 20, "payment": 10, "completeness": 10}
    result = calculate_scores(quotes_data, weights)

    s1 = result["scores"][str(v1_id)]
    s2 = result["scores"][str(v2_id)]

    # Vendor 1:
    # cost: 10000/10000 * 100 = 100
    # delivery: 7/14 * 100 = 50
    # payment: 30/60 * 100 = 50
    # completeness: 5/5 * 100 = 100
    # weighted: 100*0.6 + 50*0.2 + 50*0.1 + 100*0.1 = 60 + 10 + 5 + 10 = 85.0
    assert s1["cost_score"] == 100.0
    assert s1["delivery_score"] == 50.0
    assert s1["payment_score"] == 50.0
    assert s1["completeness_score"] == 100.0
    assert s1["final_score"] == 85.0

    # Vendor 2:
    # cost: 10000/12500 * 100 = 80.0
    # delivery: 7/7 * 100 = 100.0
    # payment: 60/60 * 100 = 100.0
    # completeness: 5/5 * 100 = 100.0
    # weighted: 80*0.6 + 100*0.2 + 100*0.1 + 100*0.1 = 48 + 20 + 10 + 10 = 88.0
    assert s2["cost_score"] == 80.0
    assert s2["delivery_score"] == 100.0
    assert s2["payment_score"] == 100.0
    assert s2["completeness_score"] == 100.0
    assert s2["final_score"] == 88.0

    # Winner should be Vendor 2
    assert result["winner_vendor_id"] == str(v2_id)


@pytest.mark.unit
def test_comparison_scoring_close_call_margin() -> None:
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()

    # Scores within 2 points
    quotes_data = [
        {
            "vendor_id": v1_id,
            "vendor_name": "Vendor A",
            "total_cost": Decimal("10000.00"),
            "lead_time_days": 10,
            "payment_terms_days": 30,
            "items_quoted": 5,
            "total_items_requested": 5,
        },
        {
            "vendor_id": v2_id,
            "vendor_name": "Vendor B",
            "total_cost": Decimal("10200.00"),
            "lead_time_days": 10,
            "payment_terms_days": 30,
            "items_quoted": 5,
            "total_items_requested": 5,
        },
    ]

    weights = {"cost": 60, "delivery": 20, "payment": 10, "completeness": 10}
    result = calculate_scores(quotes_data, weights)

    assert result["is_close"] is True
    assert result["margin"] <= 2.0


@pytest.mark.unit
def test_parse_lead_time_helper() -> None:
    # parses "5 days" / 5 / "14"
    assert parse_lead_time("5 days") == 5
    assert parse_lead_time(5) == 5
    assert parse_lead_time("14") == 14
    assert parse_lead_time("14 days") == 14
    assert parse_lead_time("Delivery Lead Time: 5 days") == 5

    # returns None when missing (never a silent 7)
    assert parse_lead_time(None) is None
    assert parse_lead_time("") is None
    assert parse_lead_time("   ") is None
    assert parse_lead_time("not specified") is None
    assert parse_lead_time("unspecified") is None
    assert parse_lead_time("N/A") is None
    assert parse_lead_time("None") is None
    assert parse_lead_time(0) is None
    assert parse_lead_time(-5) is None


@pytest.mark.unit
def test_explanation_writer_unknown_lead_time_not_invented() -> None:
    writer = TemplateExplanationWriter()
    facts = {
        "winner_vendor_id": "v1",
        "scores": {
            "v1": {
                "vendor_name": "Vendor A",
                "final_score": 90.0,
                "total_cost": "1000.00",
                "lead_time_days": None,
                "payment_terms_days": 30,
                "completeness_score": 100.0,
            }
        },
    }
    explanation = writer(facts)
    assert "not specified" in explanation
    assert "7 days" not in explanation
    assert "None days" not in explanation
