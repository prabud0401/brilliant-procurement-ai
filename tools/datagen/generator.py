"""Document generation orchestration and ground-truth emission."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
from pathlib import Path
from typing import Any

import pypdf

from tools.datagen.layouts import render_pdf_to_bytes
from tools.datagen.models import GroundTruth, ScenarioDocSpec
from tools.datagen.scanner import create_scanned_image
from tools.datagen.scenarios import get_all_scenarios

logger = logging.getLogger("tools.datagen")


def build_ground_truth(spec: ScenarioDocSpec) -> GroundTruth:
    """Build GroundTruth object from scenario specification."""
    return GroundTruth(
        doc_id=spec.doc_id,
        scenario_id=spec.scenario_id,
        doc_type=spec.doc_type,
        vendor_name=spec.vendor_name,
        vendor_trn=spec.vendor_trn,
        document_number=spec.document_number,
        document_date=spec.document_date,
        currency=spec.currency,
        po_number=spec.po_number,
        pr_number=spec.pr_number,
        payment_terms=spec.payment_terms,
        due_date=spec.due_date,
        lead_time_days=spec.lead_time_days,
        lines=spec.lines,
        subtotal=spec.subtotal,
        vat=spec.vat,
        total=spec.total,
        injection_expected=spec.injection_expected,
        injection_snippet=spec.injection_snippet or spec.hidden_text,
        injection_type=spec.injection_type,
        layout_name=spec.layout_name,
        is_scanned=spec.is_scanned,
        notes=spec.notes,
    )


def generate_documents(
    out_dir: str | Path,
    truth_dir: str | Path | None = None,
    write_png_for_scans: bool = True,
) -> dict[str, Any]:
    """Generate all scenario documents (PDF/PNG) and ground-truth JSON files.

    Returns mapping of doc_id -> {sha256, pdf_path, truth_path, is_scanned}.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    truth_path = Path(truth_dir) if truth_dir else None
    if truth_path:
        truth_path.mkdir(parents=True, exist_ok=True)

    scenarios = get_all_scenarios()
    results: dict[str, Any] = {}

    for spec in scenarios:
        pdf_bytes = render_pdf_to_bytes(spec)
        pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()

        # Write PDF to out_dir
        pdf_file = out_path / f"{spec.doc_id}.pdf"
        pdf_file.write_bytes(pdf_bytes)

        # If scanned variant, also emit standalone PNG in out_dir
        png_file = None
        if spec.is_scanned and write_png_for_scans:
            line_dicts = [
                {
                    "line_no": str(l.line_no),
                    "item_code": l.item_code,
                    "description": l.description,
                    "qty": str(l.qty),
                    "uom": l.uom,
                    "unit_price": f"{l.unit_price:.2f}",
                    "line_total": f"{l.line_total:.2f}",
                }
                for l in spec.lines
            ]
            totals_dict = {
                "Subtotal": f"{spec.subtotal:.2f}",
                "VAT (5%)": f"{spec.vat:.2f}",
                "Total": f"{spec.total:.2f}",
            }
            img = create_scanned_image(
                title=spec.doc_type.replace("_", " "),
                doc_type=spec.doc_type,
                vendor_name=spec.vendor_name,
                vendor_trn=spec.vendor_trn,
                doc_number=spec.document_number,
                doc_date=spec.document_date,
                lines=line_dicts,
                totals=totals_dict,
            )
            png_file = out_path / f"{spec.doc_id}.png"
            img.save(png_file, format="PNG")

        # Build and write ground-truth JSON
        truth = build_ground_truth(spec)
        truth_dict = truth.model_dump(mode="json")

        out_truth_file = out_path / f"{spec.doc_id}.truth.json"
        with open(out_truth_file, "w", encoding="utf-8") as f:
            json.dump(truth_dict, f, indent=2)

        if truth_path:
            target_truth = truth_path / f"{spec.doc_id}.truth.json"
            with open(target_truth, "w", encoding="utf-8") as f:
                json.dump(truth_dict, f, indent=2)

        results[spec.doc_id] = {
            "sha256": pdf_hash,
            "pdf_path": str(pdf_file),
            "png_path": str(png_file) if png_file else None,
            "truth_path": str(out_truth_file),
            "doc_type": spec.doc_type,
            "vendor_name": spec.vendor_name,
            "total": str(spec.total),
            "is_scanned": spec.is_scanned,
            "injection_expected": spec.injection_expected,
        }

    return results


def check_determinism_and_correctness() -> bool:
    """Verify determinism, footer presence, arithmetic, and fake TRN denylist."""
    scenarios = get_all_scenarios()
    logger.info("Verifying %d scenario documents...", len(scenarios))

    # Real entities denylist
    denylist = [
        "Apple",
        "Microsoft",
        "Amazon",
        "Google",
        "Etisalat",
        "Du",
        "ADNOC",
        "Emaar",
        "Emirates NBD",
        "First Abu Dhabi Bank",
    ]

    for spec in scenarios:
        # 1. Determinism test
        b1 = render_pdf_to_bytes(spec)
        b2 = render_pdf_to_bytes(spec)
        h1 = hashlib.sha256(b1).hexdigest()
        h2 = hashlib.sha256(b2).hexdigest()
        if h1 != h2:
            raise AssertionError(f"Non-deterministic render for {spec.doc_id}: {h1} != {h2}")

        # 2. Footer test
        reader = pypdf.PdfReader(io.BytesIO(b1))
        for page_idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            # For vector PDFs, pypdf extracts footer text directly
            if not spec.is_scanned and "SAMPLE – SYNTHETIC DATA" not in text:
                raise AssertionError(f"Footer missing on page {page_idx + 1} of {spec.doc_id}")

        # 3. Arithmetic validation (unless delivery note where totals are 0, or deliberate wrong VAT in s6-inv-6001-vat)
        if spec.doc_type != "delivery_note" and spec.doc_id != "s6-inv-6001-vat":
            expected_total = spec.subtotal + spec.vat
            if spec.total != expected_total:
                raise AssertionError(
                    f"Arithmetic mismatch on {spec.doc_id}: {spec.subtotal} + {spec.vat} != {spec.total}"
                )

        # 4. Denylist checks
        for entity in denylist:
            pattern = rf"\b{re.escape(entity)}\b"
            if re.search(pattern, spec.vendor_name, re.IGNORECASE):
                raise AssertionError(f"Denylist violation in {spec.doc_id}: real entity '{entity}' detected")

        # 5. Fake TRN check (15 digits, starts with 100000000)
        if spec.vendor_trn:
            if len(spec.vendor_trn) != 15:
                raise AssertionError(f"TRN length != 15 in {spec.doc_id}: '{spec.vendor_trn}'")
            if not spec.vendor_trn.startswith("100000000"):
                raise AssertionError(f"TRN not in fake test range 100000000... in {spec.doc_id}: '{spec.vendor_trn}'")

    logger.info(
        "All %d scenario documents passed determinism, footer, arithmetic, and denylist checks!", len(scenarios)
    )
    return True
