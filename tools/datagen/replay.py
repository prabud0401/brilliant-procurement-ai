"""Generate Document Intelligence and Azure OpenAI replay fixtures from ground truth."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from tools.datagen.generator import build_ground_truth
from tools.datagen.models import GroundTruth
from tools.datagen.scenarios import get_all_scenarios

logger = logging.getLogger("tools.datagen.replay")


def generate_di_fixture(truth: GroundTruth) -> dict[str, Any]:
    """Build Azure Document Intelligence analyzeResult fixture."""
    is_invoice = truth.doc_type == "invoice"
    model_id = "prebuilt-invoice" if is_invoice else "prebuilt-layout"

    # Assemble synthetic text lines and words
    text_lines: list[str] = [
        f"{truth.vendor_name}",
        f"TRN: {truth.vendor_trn}" if truth.vendor_trn else "TRN: [MISSING]",
        f"{truth.doc_type.upper().replace('_', ' ')}",
        f"Number: {truth.document_number}",
        f"Date: {truth.document_date}",
        f"Currency: {truth.currency}",
    ]
    if truth.po_number:
        text_lines.append(f"PO Number: {truth.po_number}")
    if truth.payment_terms:
        text_lines.append(f"Payment Terms: {truth.payment_terms}")
    if truth.due_date:
        text_lines.append(f"Due Date: {truth.due_date}")

    for line in truth.lines:
        text_lines.append(
            f"{line.line_no} {line.item_code} {line.description} "
            f"{line.qty} {line.uom} {line.unit_price:.2f} {line.line_total:.2f}"
        )

    text_lines.append(f"Subtotal: {truth.subtotal:.2f}")
    text_lines.append(f"VAT (5%): {truth.vat:.2f}")
    text_lines.append(f"Total: {truth.total:.2f}")

    if truth.injection_snippet:
        text_lines.append(f"Remarks: {truth.injection_snippet}")

    full_content = "\n".join(text_lines)

    # Word-level confidence simulation
    # Vary confidences for degraded or validation test cases
    default_word_conf = 0.98
    if truth.is_scanned:
        default_word_conf = 0.76  # Low confidence on scanned document
    elif truth.doc_id == "s6-inv-6001-vat":
        default_word_conf = 0.74  # Low confidence on arithmetic error document

    words: list[dict[str, Any]] = []
    lines_ocr: list[dict[str, Any]] = []
    char_offset = 0

    y_pos = 1.0
    for line_text in text_lines:
        line_len = len(line_text)
        poly = [1.0, y_pos, 7.5, y_pos, 7.5, y_pos + 0.25, 1.0, y_pos + 0.25]
        lines_ocr.append(
            {
                "content": line_text,
                "polygon": poly,
                "spans": [{"offset": char_offset, "length": line_len}],
            }
        )

        # Tokenize words
        for w in line_text.split():
            conf = default_word_conf
            # Vary a few specific word confidences below 0.80 for testing
            if w in ("VAT", "Total", "500.00") and truth.doc_id.startswith("s6"):
                conf = 0.68
            words.append(
                {
                    "content": w,
                    "polygon": [1.0, y_pos, 2.0, y_pos, 2.0, y_pos + 0.2, 1.0, y_pos + 0.2],
                    "confidence": conf,
                }
            )

        char_offset += line_len + 1
        y_pos += 0.35

    # Tables structure
    table_cells: list[dict[str, Any]] = []
    headers = ["#", "Code", "Description", "Qty", "UOM", "Price", "Total"]
    for col_idx, h in enumerate(headers):
        table_cells.append(
            {
                "rowIndex": 0,
                "columnIndex": col_idx,
                "content": h,
                "boundingRegions": [
                    {"pageNumber": 1, "polygon": [1.0, 3.0, 7.0, 3.0, 7.0, 3.2, 1.0, 3.2]}
                ],
            }
        )

    for row_idx, item in enumerate(truth.lines, start=1):
        row_vals = [
            str(item.line_no),
            item.item_code,
            item.description,
            str(item.qty),
            item.uom,
            f"{item.unit_price:.2f}",
            f"{item.line_total:.2f}",
        ]
        for col_idx, val in enumerate(row_vals):
            table_cells.append(
                {
                    "rowIndex": row_idx,
                    "columnIndex": col_idx,
                    "content": val,
                    "boundingRegions": [
                        {"pageNumber": 1, "polygon": [1.0, 3.5, 7.0, 3.5, 7.0, 3.7, 1.0, 3.7]}
                    ],
                }
            )

    # Document fields
    header_conf = default_word_conf
    fields: dict[str, Any] = {
        "VendorName": {
            "type": "string",
            "valueString": truth.vendor_name,
            "content": truth.vendor_name,
            "confidence": header_conf,
        },
        "VendorTaxId": {
            "type": "string",
            "valueString": truth.vendor_trn,
            "content": truth.vendor_trn,
            "confidence": 0.65 if not truth.vendor_trn else header_conf,
        },
        "InvoiceId": {
            "type": "string",
            "valueString": truth.document_number,
            "content": truth.document_number,
            "confidence": header_conf,
        },
        "InvoiceDate": {
            "type": "date",
            "valueDate": truth.document_date,
            "content": truth.document_date,
            "confidence": header_conf,
        },
        "InvoiceTotal": {
            "type": "currency",
            "valueCurrency": {"amount": float(truth.total), "currencySymbol": "AED"},
            "content": f"{truth.total:.2f} AED",
            "confidence": 0.72 if truth.doc_id == "s6-inv-6001-vat" else header_conf,
        },
        "SubTotal": {
            "type": "currency",
            "valueCurrency": {"amount": float(truth.subtotal), "currencySymbol": "AED"},
            "content": f"{truth.subtotal:.2f} AED",
            "confidence": header_conf,
        },
        "TotalTax": {
            "type": "currency",
            "valueCurrency": {"amount": float(truth.vat), "currencySymbol": "AED"},
            "content": f"{truth.vat:.2f} AED",
            "confidence": 0.69 if truth.doc_id == "s6-inv-6001-vat" else header_conf,
        },
    }

    if truth.po_number:
        fields["PurchaseOrderNumber"] = {
            "type": "string",
            "valueString": truth.po_number,
            "content": truth.po_number,
            "confidence": header_conf,
        }

    return {
        "status": "succeeded",
        "createdDateTime": "2026-11-19T18:00:00Z",
        "lastUpdatedDateTime": "2026-11-19T18:00:00Z",
        "analyzeResult": {
            "apiVersion": "2023-07-31",
            "modelId": model_id,
            "stringIndexType": "textElements",
            "content": full_content,
            "pages": [
                {
                    "pageNumber": 1,
                    "angle": 0.0 if not truth.is_scanned else 0.8,
                    "width": 8.5,
                    "height": 11.0,
                    "unit": "inch",
                    "words": words,
                    "lines": lines_ocr,
                }
            ],
            "tables": [
                {
                    "rowCount": len(truth.lines) + 1,
                    "columnCount": len(headers),
                    "cells": table_cells,
                }
            ],
            "documents": [
                {
                    "docType": truth.doc_type,
                    "confidence": header_conf,
                    "fields": fields,
                }
            ],
        },
    }


def generate_openai_fixture(truth: GroundTruth) -> dict[str, Any]:
    """Build Azure OpenAI chat-completions structured output response."""
    # Build strict extraction JSON per design 6.2
    header_dict: dict[str, Any] = {
        "vendor_name": {
            "value": truth.vendor_name,
            "page": 1,
            "source_text": truth.vendor_name,
        },
        "vendor_trn": {
            "value": truth.vendor_trn if truth.vendor_trn else None,
            "page": 1,
            "source_text": f"TRN: {truth.vendor_trn}" if truth.vendor_trn else "",
        },
        "document_number": {
            "value": truth.document_number,
            "page": 1,
            "source_text": f"Number: {truth.document_number}",
        },
        "document_date": {
            "value": truth.document_date,
            "page": 1,
            "source_text": f"Date: {truth.document_date}",
        },
        "po_number": (
            {
                "value": truth.po_number,
                "page": 1,
                "source_text": f"PO Number: {truth.po_number}",
            }
            if truth.po_number
            else None
        ),
        "currency": {
            "value": truth.currency,
            "page": 1,
            "source_text": f"Currency: {truth.currency}",
        },
        "payment_terms": (
            {
                "value": truth.payment_terms,
                "page": 1,
                "source_text": f"Payment Terms: {truth.payment_terms}",
            }
            if truth.payment_terms
            else None
        ),
        "due_date": (
            {
                "value": truth.due_date,
                "page": 1,
                "source_text": f"Due Date: {truth.due_date}",
            }
            if truth.due_date
            else None
        ),
        "subtotal": {
            "value": f"{truth.subtotal:.2f}",
            "page": 1,
            "source_text": f"Subtotal: {truth.subtotal:.2f}",
        },
        "vat_amount": {
            "value": f"{truth.vat:.2f}",
            "page": 1,
            "source_text": f"VAT (5%): {truth.vat:.2f}",
        },
        "total": {
            "value": f"{truth.total:.2f}",
            "page": 1,
            "source_text": f"Total: {truth.total:.2f}",
        },
    }

    lines_list: list[dict[str, Any]] = []
    for item in truth.lines:
        lines_list.append(
            {
                "line_no": item.line_no,
                "item_code": item.item_code,
                "description": item.description,
                "qty": str(item.qty),
                "uom": item.uom,
                "unit_price": f"{item.unit_price:.2f}",
                "discount": f"{item.discount:.2f}",
                "vat_rate": f"{item.vat_rate:.0f}",
                "line_total": f"{item.line_total:.2f}",
                "page": 1,
                "source_text": (
                    f"{item.line_no} {item.item_code} {item.description} "
                    f"{item.qty} {item.uom} {item.unit_price:.2f} {item.line_total:.2f}"
                ),
            }
        )

    extraction_obj = {
        "doc_type": truth.doc_type,
        "header": header_dict,
        "lines": lines_list,
    }

    content_str = json.dumps(extraction_obj, indent=2)

    return {
        "id": f"chatcmpl-replay-{truth.doc_id}",
        "object": "chat.completion",
        "created": 1732040000,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content_str,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 1250,
            "completion_tokens": len(content_str) // 4,
            "total_tokens": 1250 + (len(content_str) // 4),
        },
    }


_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPLAY_DIR = _REPO_ROOT / "eval" / "data" / "replay"


def generate_all_replay_fixtures(out_dir: str | Path = DEFAULT_REPLAY_DIR) -> int:
    """Generate .di.json and .openai.json replay fixtures for all evaluation scenarios."""
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    # Load manifest to select evaluation docs
    manifest_path = target_dir.parent / "manifest.json"
    doc_ids_filter: set[str] | None = None
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
            doc_ids_filter = {doc["doc_id"] for doc in manifest_data.get("documents", [])}

    scenarios = get_all_scenarios()
    count = 0

    for spec in scenarios:
        if doc_ids_filter and spec.doc_id not in doc_ids_filter:
            continue

        truth = build_ground_truth(spec)

        di_data = generate_di_fixture(truth)
        di_file = target_dir / f"{spec.doc_id}.di.json"
        with open(di_file, "w", encoding="utf-8") as f:
            json.dump(di_data, f, indent=2)

        openai_data = generate_openai_fixture(truth)
        openai_file = target_dir / f"{spec.doc_id}.openai.json"
        with open(openai_file, "w", encoding="utf-8") as f:
            json.dump(openai_data, f, indent=2)

        count += 1

    logger.info(
        "Generated %d replay fixture pairs (.di.json and .openai.json) into %s", count, target_dir
    )
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Document Intelligence and OpenAI replay fixtures."
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(DEFAULT_REPLAY_DIR),
        help=f"Output directory for replay fixtures (default: {DEFAULT_REPLAY_DIR})",
    )
    args = parser.parse_args()

    count = generate_all_replay_fixtures(args.out)
    print(f"SUCCESS: Generated {count} replay fixture pairs in {args.out}")


if __name__ == "__main__":
    main()
