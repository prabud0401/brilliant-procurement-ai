from decimal import Decimal
from typing import Any


def calculate_scores(
    quotes_data: list[dict[str, Any]],
    weights: dict[str, int],
) -> dict[str, Any]:
    if not quotes_data:
        return {"scores": {}, "winner_vendor_id": None, "is_close": False, "margin": 0.0}

    w_cost = weights.get("cost", 60) / 100.0
    w_del = weights.get("delivery", 20) / 100.0
    w_pay = weights.get("payment", 10) / 100.0
    w_comp = weights.get("completeness", 10) / 100.0

    # 1. Min cost
    valid_costs = [
        Decimal(str(q["total_cost"]))
        for q in quotes_data
        if Decimal(str(q.get("total_cost", 0))) > Decimal("0.00")
    ]
    min_cost = min(valid_costs) if valid_costs else Decimal("0.00")

    # 2. Min lead time
    valid_lead_times = [
        int(q["lead_time_days"])
        for q in quotes_data
        if q.get("lead_time_days") is not None and int(q["lead_time_days"]) > 0
    ]
    min_lead = min(valid_lead_times) if valid_lead_times else None

    # 3. Max payment terms
    valid_pay_terms = [
        int(q["payment_terms_days"])
        for q in quotes_data
        if q.get("payment_terms_days") is not None and int(q["payment_terms_days"]) > 0
    ]
    max_pay = max(valid_pay_terms) if valid_pay_terms else 0

    scores_by_vendor: dict[str, Any] = {}

    for q in quotes_data:
        v_id = str(q["vendor_id"])
        total_cost = Decimal(str(q.get("total_cost", 0)))
        lead_days = q.get("lead_time_days")
        pay_days = q.get("payment_terms_days")
        items_quoted = int(q.get("items_quoted", 0))
        total_items = int(q.get("total_items_requested", 1)) or 1

        # Cost score
        if total_cost > Decimal("0.00") and min_cost > Decimal("0.00"):
            cost_score = float((min_cost / total_cost) * Decimal("100.0"))
        else:
            cost_score = 0.0

        # Delivery score
        if lead_days is not None and int(lead_days) > 0 and min_lead is not None:
            delivery_score = float((min_lead / int(lead_days)) * 100.0)
        else:
            delivery_score = 0.0

        # Payment terms score
        if pay_days is not None and int(pay_days) > 0 and max_pay > 0:
            payment_score = float((int(pay_days) / max_pay) * 100.0)
        else:
            payment_score = 0.0

        # Completeness score
        completeness_score = float((items_quoted / total_items) * 100.0)

        # Final score
        final_score = round(
            cost_score * w_cost
            + delivery_score * w_del
            + payment_score * w_pay
            + completeness_score * w_comp,
            1,
        )

        scores_by_vendor[v_id] = {
            "vendor_name": q.get("vendor_name", "Vendor"),
            "cost_score": round(cost_score, 1),
            "delivery_score": round(delivery_score, 1),
            "payment_score": round(payment_score, 1),
            "completeness_score": round(completeness_score, 1),
            "final_score": final_score,
            "total_cost": str(total_cost),
            "lead_time_days": lead_days,
            "payment_terms_days": pay_days,
            "items_quoted": items_quoted,
            "total_items": total_items,
        }

    # Determine winner
    ranked = sorted(
        scores_by_vendor.items(),
        key=lambda item: item[1]["final_score"],
        reverse=True,
    )

    winner_id = ranked[0][0] if ranked else None
    is_close = False
    margin = 0.0

    if len(ranked) >= 2:
        top_score = ranked[0][1]["final_score"]
        second_score = ranked[1][1]["final_score"]
        diff = round(top_score - second_score, 1)
        if diff <= 2.0:
            is_close = True
            margin = diff

    return {
        "scores": scores_by_vendor,
        "winner_vendor_id": winner_id,
        "is_close": is_close,
        "margin": margin,
    }
