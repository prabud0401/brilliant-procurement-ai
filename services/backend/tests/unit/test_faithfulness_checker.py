import uuid
from typing import Any

import pytest

from app.comparison.explanation import (
    check_faithfulness,
    generate_explained_recommendation,
)


@pytest.mark.unit
def test_faithfulness_checker_passes_grounded_text() -> None:
    facts: dict[str, Any] = {
        "winner_vendor_id": str(uuid.uuid4()),
        "scores": {
            "v1": {
                "vendor_name": "Gulf Tech",
                "final_score": 92.5,
                "total_cost": "15000.00",
                "lead_time_days": 5,
                "payment_terms_days": 30,
                "completeness_score": 100.0,
            }
        },
        "is_close": False,
        "margin": 0.0,
    }

    grounded_text = (
        "Recommended vendor: Gulf Tech with an overall score of 92.5/100. "
        "Total cost: AED 15000.00. Delivery lead time: 5 days. Payment terms: 30 days."
    )
    assert check_faithfulness(grounded_text, facts) is True


@pytest.mark.unit
def test_faithfulness_checker_fails_on_invented_figures() -> None:
    facts: dict[str, Any] = {
        "winner_vendor_id": "v1",
        "scores": {
            "v1": {
                "vendor_name": "Gulf Tech",
                "final_score": 92.5,
                "total_cost": "15000.00",
                "lead_time_days": 5,
                "payment_terms_days": 30,
                "completeness_score": 100.0,
            }
        },
        "is_close": False,
        "margin": 0.0,
    }

    # Invented cost 18500 or 999
    unfaithful_text = (
        "Recommended vendor: Gulf Tech. Total cost: AED 18500.00 with 999 days delivery."
    )
    assert check_faithfulness(unfaithful_text, facts) is False


@pytest.mark.unit
def test_acceptance_unfaithful_explanation_replaced_by_template() -> None:
    v_id = str(uuid.uuid4())
    facts: dict[str, Any] = {
        "winner_vendor_id": v_id,
        "scores": {
            v_id: {
                "vendor_name": "Reliable Office LLC",
                "final_score": 87.0,
                "total_cost": "12000.00",
                "lead_time_days": 10,
                "payment_terms_days": 30,
                "completeness_score": 100.0,
            }
        },
        "is_close": False,
        "margin": 0.0,
    }

    # Mock an LLM that hallucinates a figure (e.g. AED 99999 or 42% discount)
    def hallucinatory_llm_writer(f: dict[str, Any]) -> str:
        return (
            "I recommend Reliable Office LLC because they give a 42% discount and price 99999 AED."
        )

    result = generate_explained_recommendation(facts, writer=hallucinatory_llm_writer)

    # Must be replaced by the template!
    assert "99999" not in result
    assert "42%" not in result
    assert "Recommended vendor: Reliable Office LLC" in result
    assert "AED 12000.00" in result
