"""Unit tests for document generator determinism."""

from __future__ import annotations

import hashlib
import tempfile

import pytest

from tools.datagen.generator import generate_documents
from tools.datagen.layouts import render_pdf_to_bytes
from tools.datagen.scenarios import get_all_scenarios


@pytest.mark.unit
def test_all_scenarios_deterministic_hashes() -> None:
    """Ensure that consecutive renders of every scenario produce bit-for-bit identical PDFs."""
    scenarios = get_all_scenarios()
    assert len(scenarios) >= 20, f"Expected at least 20 scenarios, got {len(scenarios)}"

    for spec in scenarios:
        b1 = render_pdf_to_bytes(spec)
        b2 = render_pdf_to_bytes(spec)
        h1 = hashlib.sha256(b1).hexdigest()
        h2 = hashlib.sha256(b2).hexdigest()
        assert h1 == h2, f"Document {spec.doc_id} was not deterministic: {h1} != {h2}"


@pytest.mark.unit
def test_generator_run_determinism() -> None:
    """Ensure running generate_documents twice to different folders yields matching hashes."""
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        r1 = generate_documents(out_dir=tmp1, write_png_for_scans=False)
        r2 = generate_documents(out_dir=tmp2, write_png_for_scans=False)

        assert set(r1.keys()) == set(r2.keys())
        for doc_id, meta1 in r1.items():
            meta2 = r2[doc_id]
            assert meta1["sha256"] == meta2["sha256"], f"Hash mismatch for {doc_id}"
