"""Unit tests verifying that ground truth JSON strictly matches generated PDF content and arithmetic."""

from __future__ import annotations

import io
from decimal import Decimal

import pypdf
import pytest

from tools.datagen.generator import build_ground_truth
from tools.datagen.layouts import render_pdf_to_bytes
from tools.datagen.scenarios import get_all_scenarios


@pytest.mark.unit
def test_ground_truth_matches_pdf_text() -> None:
    """PDF text extracted via pypdf must contain ground truth document number, vendor name and totals."""
    scenarios = [s for s in get_all_scenarios() if not s.is_scanned]

    for spec in scenarios:
        truth = build_ground_truth(spec)
        pdf_bytes = render_pdf_to_bytes(spec)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))

        extracted_text = " ".join((p.extract_text() or "") for p in reader.pages)

        # 1. Vendor name must be found
        assert truth.vendor_name in extracted_text, (
            f"Vendor '{truth.vendor_name}' not in PDF of {truth.doc_id}"
        )

        # 2. Document number must be found
        assert truth.document_number in extracted_text, (
            f"Doc number '{truth.document_number}' not in PDF of {truth.doc_id}"
        )

        # 3. TRN must be found (if provided)
        if truth.vendor_trn:
            assert truth.vendor_trn in extracted_text, (
                f"TRN '{truth.vendor_trn}' not in PDF of {truth.doc_id}"
            )

        # 4. Total amount must be found (formatted)
        if truth.doc_type != "delivery_note":
            formatted_total = f"{truth.total:.2f}"
            assert formatted_total in extracted_text, (
                f"Total '{formatted_total}' not in PDF of {truth.doc_id}"
            )


@pytest.mark.unit
def test_vat_arithmetic_precision() -> None:
    """Subtotal + VAT must exactly equal Total using Decimal arithmetic."""
    scenarios = get_all_scenarios()

    for spec in scenarios:
        truth = build_ground_truth(spec)

        # Delivery notes have 0 totals
        if truth.doc_type == "delivery_note":
            assert truth.total == Decimal("0.00")
            assert truth.subtotal == Decimal("0.00")
            assert truth.vat == Decimal("0.00")
            continue

        # s6-inv-6001-vat is intentionally crafted with wrong VAT calculation
        if truth.doc_id == "s6-inv-6001-vat":
            assert truth.vat == Decimal("500.00")
            assert truth.subtotal + truth.vat == truth.total
            continue

        # Standard VAT check: subtotal + vat == total
        computed_total = truth.subtotal + truth.vat
        assert truth.total == computed_total, (
            f"Total mismatch on {truth.doc_id}: {truth.total} != {computed_total}"
        )

        # 5% UAE standard rate check (with standard 1 AED tolerance for rounding)
        expected_vat_calc = (truth.subtotal * Decimal(5) / Decimal(100)).quantize(
            Decimal("0.01")
        )
        assert abs(truth.vat - expected_vat_calc) <= Decimal("1.00"), (
            f"VAT not 5% on {truth.doc_id}: {truth.vat} vs {expected_vat_calc}"
        )
