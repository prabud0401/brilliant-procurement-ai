"""Unit tests for prompt injection detection in Q&A questions per US-29 and design 7.5."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.extraction.injection_detector import scan_text_for_injection


@pytest.mark.unit
def test_injection_cases_detected() -> None:
    # Resolve eval/data/injection_cases.json relative to repository root
    repo_root = Path(__file__).resolve().parents[3]
    injection_file = repo_root / "eval" / "data" / "injection_cases.json"
    if not injection_file.exists():
        repo_root = Path(__file__).resolve().parents[4]
        injection_file = repo_root / "eval" / "data" / "injection_cases.json"

    assert injection_file.exists(), f"injection_cases.json not found at {injection_file}"

    with open(injection_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    # QA-targeted injection categories
    qa_categories = {
        "system_prompt_leak",
        "data_exfiltration",
        "cross_tenant_access",
        "direct_instruction",
        "setting_tamper",
    }

    tested_count = 0
    for case in cases:
        if case.get("category") in qa_categories:
            text = case["text"]
            findings = scan_text_for_injection(text, page=1)
            assert len(findings) > 0, f"Failed to detect injection case: {case['case_id']} - {text}"
            tested_count += 1

    assert tested_count >= 5


@pytest.mark.unit
def test_clean_procurement_questions_not_flagged() -> None:
    clean_questions = [
        "What are Gulf Line IT Trading's payment terms on quote Q-1042?",
        "What is the total amount including VAT on invoice INV-2291?",
        "Which vendor offered the shortest delivery lead time for laptops?",
        "How many ergonomic chairs were delivered under delivery note DN-1090?",
    ]

    for q in clean_questions:
        findings = scan_text_for_injection(q, page=1)
        assert len(findings) == 0, f"False positive injection flag on clean question: {q}"
