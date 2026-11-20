"""Confidence scoring and evidence span matching per design 6.3."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from app.ai.schemas import OCRPage, OCRWord


def match_evidence_span(
    source_text: str | None,
    page: OCRPage | None,
) -> tuple[float, dict[str, Any] | None, bool]:
    """Find evidence span in OCR page words.

    Returns:
    - lowest_word_conf: float
    - bbox: dict or None
    - found: bool (whether source_text was grounded in OCR)
    """
    if not source_text or not source_text.strip() or not page or not page.words:
        return 0.50, None, False

    clean_source = source_text.strip().lower()
    source_tokens = re.findall(r"\w+", clean_source)
    if not source_tokens:
        return 0.50, None, False

    # Look for contiguous matching words first
    page_words = page.words
    n_tokens = len(source_tokens)
    best_match_words: list[OCRWord] = []

    # Slide window over page words
    for i in range(len(page_words) - n_tokens + 1):
        window = page_words[i : i + n_tokens]
        window_tokens = [re.sub(r"\W+", "", w.content.lower()) for w in window]
        if window_tokens == source_tokens:
            best_match_words = window
            break

    # If no contiguous exact match, try token intersection
    if not best_match_words:
        source_set = set(source_tokens)
        matched = [w for w in page_words if re.sub(r"\W+", "", w.content.lower()) in source_set]
        if len(matched) >= len(source_set) * 0.7 and len(matched) > 0:
            best_match_words = matched

    if not best_match_words:
        # Check if full source substring appears in page text
        page_full_text = " ".join(w.content for w in page_words).lower()
        if clean_source in page_full_text:
            # Source text appears in OCR but individual token alignment was partial
            avg_conf = sum(w.confidence for w in page_words) / len(page_words)
            return avg_conf, None, True
        return 0.50, None, False

    lowest_word_conf = min(w.confidence for w in best_match_words)

    # Compute bounding polygon around matched words
    all_x: list[float] = []
    all_y: list[float] = []
    for w in best_match_words:
        if w.polygon and len(w.polygon) >= 8:
            all_x.extend(w.polygon[0::2])
            all_y.extend(w.polygon[1::2])

    bbox: dict[str, Any] | None = None
    if all_x and all_y:
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        bbox = {
            "page": page.page_number,
            "polygon": [min_x, min_y, max_x, min_y, max_x, max_y, min_x, max_y],
            "box": [min_x, min_y, max_x, max_y],
        }

    return lowest_word_conf, bbox, True


def calculate_field_confidence(
    field_name: str,
    raw_value: str | None,
    source_text: str | None,
    page: OCRPage | None,
    di_field_value: str | None = None,
    is_invoice: bool = False,
    has_conflicting_value: bool = False,
    was_cleaned: bool = False,
    parse_failed: bool = False,
    has_arithmetic_mismatch: bool = False,
) -> tuple[Decimal, dict[str, Any] | None]:
    """Calculate calibrated confidence score per design 6.3.

    Signals:
    - Base: lowest word confidence in matched evidence span.
    - Missing evidence: capped at 0.50.
    - Unmatched value (cleaned value not in page or source text): capped at 0.50.
    - Value modified by cleanup: capped at 0.75 (below AI_LOW_CONFIDENCE_THRESHOLD 0.80).
    - Arithmetic mismatch: capped at 0.70.
    - Format failure or parse failed: capped at 0.40.
    - Disagreement with prebuilt-invoice: capped at 0.60.
    - Conflicting duplicate value: capped at 0.70.
    """
    if raw_value is None or raw_value.strip() == "":
        return Decimal("0.0000"), None

    span_conf, bbox, found = match_evidence_span(source_text, page)
    score = span_conf

    # 1. Evidence grounding cap
    if not found:
        score = min(score, 0.50)

    clean_val = raw_value.strip()

    # 2. Check if the value itself appears in source text or page words
    page_words_text = " ".join(w.content for w in page.words).lower() if page and page.words else ""
    src_text_lower = (source_text or "").lower()

    if field_name in ("subtotal", "vat_amount", "total", "unit_price", "line_total", "vendor_trn"):
        val_digits = re.sub(r"\D", "", clean_val)
        val_in_doc = (
            (
                (val_digits in re.sub(r"\D", "", src_text_lower))
                or (val_digits in re.sub(r"\D", "", page_words_text))
            )
            if val_digits
            else False
        )
    else:
        clean_text_norm = re.sub(r"\W+", " ", clean_val.lower()).strip()
        val_in_doc = (
            (
                (clean_text_norm in re.sub(r"\W+", " ", src_text_lower))
                or (clean_text_norm in re.sub(r"\W+", " ", page_words_text))
            )
            if clean_text_norm
            else False
        )

    if not val_in_doc:
        score = min(score, 0.50)

    # 3. Value cleanup penalty: if cleanup had to alter the value, cap below 0.80
    if was_cleaned:
        score = min(score, 0.75)

    # 4. Arithmetic mismatch penalty
    if has_arithmetic_mismatch:
        score = min(score, 0.70)

    # 5. Parse failure penalty
    if parse_failed:
        score = min(score, 0.40)

    # 6. Agreement with prebuilt-invoice model
    if is_invoice and di_field_value is not None:
        clean_ext = re.sub(r"[\s,\.\-]+", "", clean_val.lower())
        clean_di = re.sub(r"[\s,\.\-]+", "", str(di_field_value).lower())
        if clean_ext != clean_di and clean_ext not in clean_di and clean_di not in clean_ext:
            score = min(score, 0.60)

    # 7. Format check for field type
    if "date" in field_name:
        # Date format check (e.g. YYYY-MM-DD or DD/MM/YYYY)
        if not re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}", clean_val):
            score = min(score, 0.40)
    elif field_name in ("subtotal", "vat_amount", "total", "unit_price", "line_total"):
        # Amount format check
        try:
            cleaned_num = re.sub(r"[^\d\.\-]", "", clean_val)
            float(cleaned_num)
        except ValueError:
            score = min(score, 0.40)
    elif field_name == "vendor_trn":
        # TRN 15 digits check
        digits = re.sub(r"\D", "", clean_val)
        if len(digits) != 15:
            score = min(score, 0.40)

    # 8. Duplicate conflicting values
    if has_conflicting_value:
        score = min(score, 0.70)

    # Clamp between 0 and 1
    score = max(0.0, min(1.0, score))
    return Decimal(f"{score:.4f}"), bbox
