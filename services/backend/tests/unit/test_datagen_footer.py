"""Unit tests verifying that every generated page includes the mandatory synthetic footer."""

from __future__ import annotations

import io

import pypdf
import pytest

from tools.datagen.layouts import render_pdf_to_bytes
from tools.datagen.scenarios import get_all_scenarios

MANDATORY_FOOTER = "SAMPLE – SYNTHETIC DATA"


@pytest.mark.unit
def test_footer_present_on_all_pages_vector_pdfs() -> None:
    """Every page of every generated vector PDF must contain the mandatory synthetic data footer."""
    scenarios = [s for s in get_all_scenarios() if not s.is_scanned]
    assert len(scenarios) >= 15

    for spec in scenarios:
        pdf_bytes = render_pdf_to_bytes(spec)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        assert len(reader.pages) > 0, f"No pages in PDF for {spec.doc_id}"

        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            assert MANDATORY_FOOTER in text, (
                f"Footer missing on page {idx + 1} of {spec.doc_id}"
            )


@pytest.mark.unit
def test_footer_present_in_scanned_layout() -> None:
    """Scanned images must also be generated with the mandatory synthetic footer."""
    scanned_scenarios = [s for s in get_all_scenarios() if s.is_scanned]
    assert len(scanned_scenarios) >= 2, (
        "Must have at least 2 scanned document scenarios"
    )

    for spec in scanned_scenarios:
        pdf_bytes = render_pdf_to_bytes(spec)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        # Scanned PDFs contain a canvas footer drawn by SyntheticDocCanvas
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            assert MANDATORY_FOOTER in text, (
                f"Synthetic footer missing on canvas of scanned doc {spec.doc_id}"
            )
