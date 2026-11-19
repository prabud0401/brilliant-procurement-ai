import difflib
import uuid
from decimal import Decimal
from typing import Any

from app.core.models import ExtractedLine, POLine


def execute_three_way_match(
    po_lines: list[POLine],
    invoice_lines: list[ExtractedLine],
    dn_lines_by_po_line: dict[uuid.UUID, list[Decimal]],
    invoice_vat: Decimal,
    tolerances: dict[str, Any],
) -> dict[str, Any]:
    qty_tol_units = Decimal(str(tolerances.get("invoiced_vs_received_qty_max_units", 0)))
    price_tol_pct = Decimal(str(tolerances.get("unit_price_variance_pct", 2.0)))
    price_tol_max_aed = Decimal(str(tolerances.get("unit_price_variance_max_aed", "50.00")))
    vat_max_diff_aed = Decimal(str(tolerances.get("vat_max_difference_aed", "1.00")))

    matched_lines_out: list[dict[str, Any]] = []
    exceptions_out: list[dict[str, Any]] = []

    # Map PO lines for pairing
    available_po_lines = list(po_lines)

    for inv_line in invoice_lines:
        line_no = inv_line.line_no
        invoiced_qty = inv_line.qty or Decimal("1.00")
        inv_unit_price = inv_line.unit_price or Decimal("0.00")

        # 1. Pair with PO line
        paired_po_line: POLine | None = None
        # Try item code / description match
        if inv_line.item_code:
            for pl in available_po_lines:
                if inv_line.item_code.lower() in pl.description.lower():
                    paired_po_line = pl
                    break

        if not paired_po_line and inv_line.description:
            best_score = 0.0
            best_pl: POLine | None = None
            for pl in available_po_lines:
                score = difflib.SequenceMatcher(
                    None, inv_line.description.lower(), pl.description.lower()
                ).ratio()
                if score > best_score:
                    best_score = score
                    best_pl = pl
            if best_score >= 0.35 and best_pl:
                paired_po_line = best_pl

        if not paired_po_line and available_po_lines:
            paired_po_line = available_po_lines[0]

        if not paired_po_line:
            # Unmatched item
            line_data = {
                "po_line_id": None,
                "invoice_line_id": inv_line.id,
                "ordered_qty": None,
                "received_qty": None,
                "invoiced_qty": invoiced_qty,
                "po_unit_price": None,
                "inv_unit_price": inv_unit_price,
                "variance_aed": Decimal("0.00"),
                "status": "exception",
                "reason": f"Line {line_no}: unmatched invoice line",
            }
            matched_lines_out.append(line_data)
            exceptions_out.append(
                {
                    "match_line_data": line_data,
                    "kind": "unmatched_item",
                    "reason": f"Line {line_no}: item could not be matched to any PO line",
                    "amount_impact_aed": invoiced_qty * inv_unit_price,
                }
            )
            continue

        # Paired with PO line
        ordered_qty = paired_po_line.qty
        received_qty_list = dn_lines_by_po_line.get(paired_po_line.id, [])
        received_qty = sum(received_qty_list, Decimal("0.00"))
        po_unit_price = paired_po_line.unit_price

        line_status = "matched"
        line_reason = None
        variance = (inv_unit_price - po_unit_price) * invoiced_qty

        # Check QTY
        if invoiced_qty > received_qty + qty_tol_units:
            line_status = "exception"
            reason_str = f"Line {line_no}: invoiced {invoiced_qty}, received {received_qty}"
            line_reason = reason_str
            impact = (invoiced_qty - received_qty) * inv_unit_price
            exceptions_out.append(
                {
                    "match_line_data": None,  # will attach line id
                    "po_line_id": paired_po_line.id,
                    "invoice_line_id": inv_line.id,
                    "kind": "qty_variance",
                    "reason": reason_str,
                    "amount_impact_aed": impact,
                }
            )

        # Check Price
        allowed_variance = min(
            (price_tol_pct / Decimal("100.0")) * po_unit_price * invoiced_qty,
            price_tol_max_aed,
        )

        if variance > allowed_variance:
            line_status = "exception"
            reason_str = (
                f"Line {line_no}: price variance AED {variance:.2f} exceeds "
                f"tolerance (PO: {po_unit_price}, Inv: {inv_unit_price})"
            )
            line_reason = reason_str
            exceptions_out.append(
                {
                    "match_line_data": None,
                    "po_line_id": paired_po_line.id,
                    "invoice_line_id": inv_line.id,
                    "kind": "price_variance",
                    "reason": reason_str,
                    "amount_impact_aed": variance,
                }
            )
        elif variance > Decimal("0.00") and line_status != "exception":
            line_status = "within_tolerance"
            line_reason = f"Line {line_no}: price variance within tolerance"

        line_data = {
            "po_line_id": paired_po_line.id,
            "invoice_line_id": inv_line.id,
            "ordered_qty": ordered_qty,
            "received_qty": received_qty,
            "invoiced_qty": invoiced_qty,
            "po_unit_price": po_unit_price,
            "inv_unit_price": inv_unit_price,
            "variance_aed": variance,
            "status": line_status,
            "reason": line_reason,
        }
        matched_lines_out.append(line_data)

    # VAT Check
    total_inv_subtotal = sum(
        (mline["invoiced_qty"] * mline["inv_unit_price"] for mline in matched_lines_out),
        Decimal("0.00"),
    )
    expected_vat = (total_inv_subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
    vat_diff = abs(invoice_vat - expected_vat)
    if vat_diff > vat_max_diff_aed:
        exceptions_out.append(
            {
                "match_line_data": None,
                "po_line_id": None,
                "invoice_line_id": None,
                "kind": "vat_mismatch",
                "reason": (
                    f"VAT difference AED {vat_diff:.2f} exceeds tolerance AED {vat_max_diff_aed}"
                ),
                "amount_impact_aed": vat_diff,
            }
        )

    # Overall status
    if exceptions_out:
        overall_status = "exception"
    elif any(mline["status"] == "within_tolerance" for mline in matched_lines_out):
        overall_status = "within_tolerance"
    else:
        overall_status = "matched"

    return {
        "overall_status": overall_status,
        "lines": matched_lines_out,
        "exceptions": exceptions_out,
    }
