import re
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ExplanationWriter(Protocol):
    def __call__(self, facts: dict[str, Any]) -> str: ...


class TemplateExplanationWriter:
    """Deterministic default explanation writer based purely on confirmed facts."""

    def __call__(self, facts: dict[str, Any]) -> str:
        winner_id = facts.get("winner_vendor_id")
        scores = facts.get("scores", {})
        winner_info = scores.get(str(winner_id), {}) if winner_id else {}

        winner_name = winner_info.get("vendor_name", "the recommended vendor")
        winner_score = winner_info.get("final_score", 0.0)
        total_cost = winner_info.get("total_cost", "0.00")
        lead_days = winner_info.get("lead_time_days", "N/A")
        pay_days = winner_info.get("payment_terms_days", "N/A")
        comp = winner_info.get("completeness_score", 100.0)

        lead_str = f"{lead_days} days" if lead_days != "N/A" else "unspecified"
        pay_str = f"{pay_days} days" if pay_days != "N/A" else "unspecified"

        text = (
            f"Recommended vendor: {winner_name} with an overall score of {winner_score}/100. "
            f"Total cost: AED {total_cost}. Delivery lead time: {lead_str}. "
            f"Payment terms: {pay_str}. Completeness: {comp:.0f}%."
        )

        if facts.get("is_close", False):
            margin = facts.get("margin", 0.0)
            other_vendors = [v["vendor_name"] for vid, v in scores.items() if vid != str(winner_id)]
            second_name = other_vendors[0] if other_vendors else "the second vendor"
            text += (
                f" The margin between {winner_name} and {second_name} is {margin} points; "
                f"a difference in delivery or cost could shift the recommendation."
            )

        return text


def _extract_all_numbers(data: Any) -> set[str]:
    """Recursively harvest all numbers from facts into canonical representations."""
    results: set[str] = set()

    def _collect(val: Any) -> None:
        if isinstance(val, (int, float)):
            results.add(str(val))
            # Also add int representation if float ending in .0
            if isinstance(val, float) and val.is_integer():
                results.add(str(int(val)))
            # Also add float formatted to 1 and 2 decimal places
            results.add(f"{val:.1f}")
            results.add(f"{val:.2f}")
        elif isinstance(val, str):
            # Try to match numbers inside strings
            found = re.findall(r"\b\d+(?:\.\d+)?\b", val)
            for num in found:
                results.add(num)
                try:
                    flt = float(num)
                    results.add(str(flt))
                    if flt.is_integer():
                        results.add(str(int(flt)))
                    results.add(f"{flt:.1f}")
                    results.add(f"{flt:.2f}")
                except ValueError:
                    pass
        elif isinstance(val, dict):
            for v in val.values():
                _collect(v)
        elif isinstance(val, (list, tuple, set)):
            for v in val:
                _collect(v)

    _collect(data)
    # Common standard integers that can appear as counts, denominators (e.g. /100), etc.
    results.update({"1", "2", "3", "4", "5", "60", "20", "10", "100", "0"})
    return results


def check_faithfulness(candidate_text: str, facts: dict[str, Any]) -> bool:
    """Check that every number in the text appears in the facts JSON.

    If an invented number is found, return False.
    """
    allowed_numbers = _extract_all_numbers(facts)
    candidate_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", candidate_text)

    for num in candidate_numbers:
        # Check direct or float-equivalent presence
        if num in allowed_numbers:
            continue
        try:
            flt = float(num)
            if (
                str(flt) in allowed_numbers
                or (flt.is_integer() and str(int(flt)) in allowed_numbers)
                or f"{flt:.1f}" in allowed_numbers
                or f"{flt:.2f}" in allowed_numbers
            ):
                continue
        except ValueError:
            pass

        # Number not found in facts -> unfaithful!
        return False

    return True


def generate_explained_recommendation(
    facts: dict[str, Any],
    writer: ExplanationWriter | None = None,
) -> str:
    template_writer = TemplateExplanationWriter()
    template_text = template_writer(facts)

    if writer is not None:
        try:
            candidate = writer(facts)
            if candidate and check_faithfulness(candidate, facts):
                return candidate
        except Exception:
            pass

    return template_text
