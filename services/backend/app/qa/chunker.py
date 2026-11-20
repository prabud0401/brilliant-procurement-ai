"""Document chunker creating page-bounded chunks, Markdown tables, and facts per design 6.6."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any, Sequence

from app.ai.schemas import OCRResult
from app.extraction.injection_detector import scan_text_for_injection

APPROX_TOKEN_WORDS = 350  # ~500 tokens
APPROX_OVERLAP_WORDS = 35  # ~50 tokens


@dataclass
class ChunkDraft:
    page: int
    chunk_no: int
    text: str
    content_hash: str = ""


def format_table_to_markdown(table: dict[str, Any]) -> str:
    """Format OCR table structure into a Markdown table.

    Splits rows and repeats headers if table exceeds token limit.
    """
    row_count = table.get("rowCount", 0)
    col_count = table.get("columnCount", 0)
    cells = table.get("cells", [])
    if row_count == 0 or col_count == 0 or not cells:
        return ""

    grid = [["" for _ in range(col_count)] for _ in range(row_count)]
    for cell in cells:
        r = cell.get("rowIndex", 0)
        c = cell.get("columnIndex", 0)
        if r < row_count and c < col_count:
            content = str(cell.get("content", "")).replace("\n", " ").strip()
            grid[r][c] = content

    header_row = "| " + " | ".join(grid[0]) + " |"
    separator_row = "| " + " | ".join(["---"] * col_count) + " |"

    data_rows: list[str] = []
    for row in grid[1:]:
        data_rows.append("| " + " | ".join(row) + " |")

    # If table has many rows, chunk rows with header repeated
    MAX_ROWS_PER_TABLE_CHUNK = 20
    if len(data_rows) > MAX_ROWS_PER_TABLE_CHUNK:
        table_chunks: list[str] = []
        for i in range(0, len(data_rows), MAX_ROWS_PER_TABLE_CHUNK):
            slice_rows = data_rows[i : i + MAX_ROWS_PER_TABLE_CHUNK]
            table_chunks.append("\n".join([header_row, separator_row] + slice_rows))
        return "\n\n".join(table_chunks)

    return "\n".join([header_row, separator_row] + data_rows)


def build_page_text_chunks(
    page_number: int,
    text_content: str,
    table_markdowns: list[str],
) -> list[str]:
    """Build page-bounded chunks (~500 tokens, 50-token overlap)."""
    # Filter out injection lines
    clean_lines: list[str] = []
    for line in text_content.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if scan_text_for_injection(line_stripped, page=page_number):
            continue
        clean_lines.append(line_stripped)

    # Combine text and tables on this page
    blocks: list[str] = []
    if clean_lines:
        blocks.append("\n".join(clean_lines))
    for t_md in table_markdowns:
        if t_md:
            blocks.append(t_md)

    combined_page_text = "\n\n".join(blocks).strip()
    if not combined_page_text:
        return []

    words = combined_page_text.split()
    if len(words) <= APPROX_TOKEN_WORDS:
        return [combined_page_text]

    # Split into overlapping windows within this page
    chunks: list[str] = []
    start = 0
    step = max(1, APPROX_TOKEN_WORDS - APPROX_OVERLAP_WORDS)
    while start < len(words):
        chunk_words = words[start : start + APPROX_TOKEN_WORDS]
        chunks.append(" ".join(chunk_words))
        start += step

    return chunks


def build_facts_chunk(
    doc_id: uuid.UUID,
    doc_type: str,
    vendor_name: str | None,
    confirmed_fields: Sequence[Any],
    confirmed_lines: Sequence[Any],
) -> str:
    """Build a document facts chunk from confirmed field values cited with pages."""
    lines: list[str] = [
        "Document Facts Summary:",
        f"Document ID: {doc_id}",
        f"Document Type: {doc_type} (Page 1)",
    ]
    if vendor_name:
        lines.append(f"Vendor Name: {vendor_name} (Page 1)")

    for f in confirmed_fields:
        f_name = getattr(f, "name", None) or ""
        f_val = getattr(f, "value_raw", None) or ""
        f_page = getattr(f, "page", 1)
        if f_val and f_name:
            label = f_name.replace("_", " ").title()
            lines.append(f"{label}: {f_val} (Page {f_page})")

    if confirmed_lines:
        lines.append("Confirmed Line Items:")
        for line in confirmed_lines:
            line_no = getattr(line, "line_no", 1)
            desc = getattr(line, "description", None) or getattr(line, "item_code", None) or "Item"
            qty = getattr(line, "qty", "")
            unit_price = getattr(line, "unit_price", "")
            line_total = getattr(line, "line_total", "")
            l_page = getattr(line, "page", 1)
            lines.append(
                f"- Line {line_no}: {desc} | Qty: {qty} | "
                f"Unit Price: {unit_price} | Line Total: {line_total} (Page {l_page})"
            )

    return "\n".join(lines)


def build_document_chunks(
    document: Any,
    ocr_result: OCRResult | None,
    confirmed_fields: Sequence[Any],
    confirmed_lines: Sequence[Any],
    vendor_name: str | None = None,
) -> list[ChunkDraft]:
    """Build all chunks for a confirmed document: page-bounded layout chunks

    plus one document facts chunk. Re-confirming changed content replaces chunks.
    Prompt injection passages are excluded.
    """
    raw_chunks: list[tuple[int, str]] = []  # (page, text)

    # 1. Layout / OCR Chunks per page
    if ocr_result and ocr_result.pages:
        # Index tables by page number
        tables_by_page: dict[int, list[str]] = {}
        for tbl in ocr_result.tables:
            cells = tbl.get("cells", [])
            t_page = 1
            if cells:
                regions = cells[0].get("boundingRegions", [])
                if regions:
                    t_page = regions[0].get("pageNumber", 1)
            md = format_table_to_markdown(tbl)
            if md:
                tables_by_page.setdefault(t_page, []).append(md)

        for page in ocr_result.pages:
            p_no = page.page_number
            p_lines = [line_obj.content for line_obj in page.lines]
            p_text = "\n".join(p_lines)
            t_mds = tables_by_page.get(p_no, [])

            page_chunks = build_page_text_chunks(p_no, p_text, t_mds)
            for c_text in page_chunks:
                raw_chunks.append((p_no, c_text))

    # 2. Document Facts chunk from confirmed fields and lines
    facts_text = build_facts_chunk(
        doc_id=document.id,
        doc_type=document.doc_type,
        vendor_name=vendor_name,
        confirmed_fields=confirmed_fields,
        confirmed_lines=confirmed_lines,
    )
    raw_chunks.append((1, facts_text))

    # 3. Compute overall content hash across all chunks
    combined_content = "\n---\n".join(text for _, text in raw_chunks)
    content_hash = hashlib.sha256(combined_content.encode("utf-8")).hexdigest()

    # 4. Create ChunkDraft objects
    result_chunks: list[ChunkDraft] = []
    for idx, (p_num, c_text) in enumerate(raw_chunks, start=1):
        result_chunks.append(
            ChunkDraft(
                page=p_num,
                chunk_no=idx,
                text=c_text,
                content_hash=content_hash,
            )
        )

    return result_chunks
