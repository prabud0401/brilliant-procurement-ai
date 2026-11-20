"""Extraction service orchestrating OCR, injection detection, schema extraction, and checks."""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.cache import get_cached_extraction, store_cached_extraction
from app.ai.cost import calculate_cost_aed, check_daily_budget
from app.ai.factory import get_document_analyzer, get_llm_client
from app.ai.normalize import CleanupMetadata, cleanup_extraction_result
from app.audit.service import record as record_audit
from app.core.errors import ProblemException
from app.core.models import (
    Document,
    ExtractedField,
    ExtractedLine,
    Extraction,
    InjectionFlag,
)
from app.documents.storage import get_storage
from app.extraction.confidence import calculate_field_confidence
from app.extraction.injection_detector import scan_text_for_injection
from app.extraction.validation import parse_decimal, validate_extracted_data
from app.observability.ai_events import emit_ai_metric_event

logger = logging.getLogger("extraction.service")


def run_extraction(session: Session, document_id: uuid.UUID) -> Extraction:
    """Run full extraction pipeline on a document."""
    document = session.execute(
        select(Document).where(Document.id == document_id)
    ).scalar_one_or_none()
    if not document:
        raise ValueError(f"Document {document_id} not found")

    document.status = "processing"
    session.flush()

    # 1. Enforce daily AI budget
    check_daily_budget(session)

    # 2. Download original file bytes
    storage = get_storage()
    file_bytes = storage.download(document.blob_path)

    # 3. Document Intelligence OCR analysis
    analyzer = get_document_analyzer()
    ocr_di_model = "prebuilt-invoice" if document.doc_type == "invoice" else "prebuilt-layout"
    ocr_result = analyzer.analyze(
        file_bytes=file_bytes,
        mime=document.mime,
        doc_type_hint=document.doc_type,
        file_sha256=document.file_sha256,
    )

    # Save raw OCR JSON to blob storage
    raw_ocr_path = f"ocr/{document.id}.json"
    try:
        storage.upload(
            raw_ocr_path,
            ocr_result.model_dump_json().encode("utf-8"),
            content_type="application/json",
        )
    except Exception as exc:
        logger.warning("Could not upload raw OCR json: %s", exc)

    # 4. Prompt-injection defence screening (design 7.5, US-29)
    findings = []
    if ocr_result.pages:
        for p in ocr_result.pages:
            page_text = " ".join(w.content for w in p.words)
            findings.extend(scan_text_for_injection(page_text, page=p.page_number))
    if not findings and ocr_result.content:
        findings.extend(scan_text_for_injection(ocr_result.content, page=1))

    if findings:
        document.suspicious = True
        for finding in findings:
            flag = InjectionFlag(
                id=uuid.uuid4(),
                document_id=document.id,
                page=finding.page,
                detector=finding.detector,
                score=finding.score,
                snippet_hash=finding.snippet_hash,
            )
            session.add(flag)
            # Store ONLY snippet hash and page in audit, never raw text (design 7.5)
            record_audit(
                session=session,
                actor=None,
                action="injection.flagged",
                entity_type="document",
                entity_id=document.id,
                reason="Prompt-injection pattern detected during extraction screening",
                after={
                    "page": finding.page,
                    "snippet_hash": finding.snippet_hash,
                    "score": str(finding.score),
                },
            )

    # 4b. Auto-classify untyped documents (US-01 / F04)
    cls_tokens_in = 0
    cls_tokens_out = 0
    if document.doc_type in (None, "other"):
        first_page_text = ""
        if ocr_result.pages and ocr_result.pages[0].words:
            first_page_text = " ".join(w.content for w in ocr_result.pages[0].words)
        if not first_page_text:
            first_page_text = ocr_result.content or ""

        try:
            check_daily_budget(session)
            llm_client = get_llm_client()
            if hasattr(llm_client, "classify_with_usage"):
                label, cls_meta = llm_client.classify_with_usage(first_page_text)
            else:
                label = llm_client.classify(first_page_text)
                cls_meta = getattr(llm_client, "last_usage", None) or {}

            cls_tokens_in = cls_meta.get("tokens_in", 0)
            cls_tokens_out = cls_meta.get("tokens_out", 0)

            valid_labels = {"quote", "purchase_order", "delivery_note", "invoice"}
            if label in valid_labels:
                before_doc_type = document.doc_type
                document.doc_type = label
                record_audit(
                    session=session,
                    actor=None,
                    action="document.classified",
                    entity_type="document",
                    entity_id=document.id,
                    before={"doc_type": before_doc_type},
                    after={"doc_type": document.doc_type},
                )
            elif document.doc_type is None:
                document.doc_type = "other"
        except ProblemException as pe:
            if pe.code == "AI_BUDGET_EXCEEDED":
                raise
            logger.warning("Auto-classification failed for document %s: %s", document.id, pe)
            if document.doc_type is None:
                document.doc_type = "other"
        except Exception as exc:
            logger.warning("Auto-classification failed for document %s: %s", document.id, exc)
            if document.doc_type is None:
                document.doc_type = "other"

    # 5. Structured LLM extraction with response caching (NFR-COST-03)
    prompt_version = "prompts/extract_v1.md"
    cached = get_cached_extraction(document.file_sha256, prompt_version)
    if cached is not None:
        extraction_result, metadata = cached
    else:
        llm = get_llm_client()
        extraction_result, metadata = llm.extract(
            ocr_result=ocr_result,
            doc_type=document.doc_type,
            file_sha256=document.file_sha256,
        )
        store_cached_extraction(document.file_sha256, prompt_version, extraction_result, metadata)

    # Ensure deterministic cleanup is applied and metadata available
    cleanup_meta: CleanupMetadata | None = metadata.get("cleanup")
    if cleanup_meta is None:
        extraction_result, cleanup_meta = cleanup_extraction_result(extraction_result)

    # If doc_type was generic "other", update from classified type
    if document.doc_type == "other" and extraction_result.doc_type:
        dt = extraction_result.doc_type.lower()
        if dt in ("quote", "quotation"):
            document.doc_type = "quote"
        elif dt in ("purchase_order", "po"):
            document.doc_type = "purchase_order"
        elif dt in ("delivery_note", "dn"):
            document.doc_type = "delivery_note"
        elif dt == "invoice":
            document.doc_type = "invoice"

    # 6. Cost and token metering
    tokens_in = metadata.get("tokens_in", 0) + cls_tokens_in
    tokens_out = metadata.get("tokens_out", 0) + cls_tokens_out
    llm_model = metadata.get("model", "gpt-4o-mini")
    est_cost = calculate_cost_aed(tokens_in, tokens_out, model=llm_model)
    latency_ms = metadata.get("latency_ms", 0)

    emit_ai_metric_event(
        task="extraction",
        model=llm_model,
        prompt_version=prompt_version,
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        estimated_cost=est_cost,
        refusal_flag=False,
        injection_flag=bool(findings),
    )

    # Determine extraction version number
    prev_count = session.execute(
        select(func.count(Extraction.id)).where(Extraction.document_id == document.id)
    ).scalar_one()
    version = prev_count + 1

    extraction = Extraction(
        id=uuid.uuid4(),
        document_id=document.id,
        version=version,
        di_model=ocr_di_model,
        llm_model=llm_model,
        prompt_version=prompt_version,
        raw_ocr_path=raw_ocr_path,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        est_cost=est_cost,
        latency_ms=latency_ms,
        status="completed",
    )
    session.add(extraction)
    session.flush()

    # 7. Validation checks
    raw_header_values: dict[str, str | None] = {}
    for k, v in extraction_result.header.items():
        raw_header_values[k] = v.value if v else None

    raw_lines = [line_item.model_dump() for line_item in extraction_result.lines]
    val_result = validate_extracted_data(session, document, raw_header_values, raw_lines)

    if val_result.matched_vendor_id:
        document.vendor_id = val_result.matched_vendor_id
    if val_result.duplicate_doc_id:
        document.duplicate_of = val_result.duplicate_doc_id

    # 8. Create ExtractedField rows with confidence and validation status
    for fname, fval in extraction_result.header.items():
        if fval is None:
            continue

        page_num = fval.page or 1
        page_obj = None
        if ocr_result.pages and len(ocr_result.pages) >= page_num:
            page_obj = ocr_result.pages[page_num - 1]
        elif ocr_result.pages:
            page_obj = ocr_result.pages[0]

        # Invoices: check prebuilt field agreement
        di_val: str | None = None
        if document.doc_type == "invoice" and ocr_result.documents:
            di_fields = ocr_result.documents[0].get("fields", {})
            mapping = {
                "vendor_name": "VendorName",
                "vendor_trn": "VendorTaxId",
                "document_number": "InvoiceId",
                "document_date": "InvoiceDate",
                "total": "InvoiceTotal",
                "subtotal": "SubTotal",
                "vat_amount": "TotalTax",
            }
            if fname in mapping and mapping[fname] in di_fields:
                di_val = di_fields[mapping[fname]].get("content")

        conf, bbox = calculate_field_confidence(
            field_name=fname,
            raw_value=fval.value,
            source_text=fval.source_text,
            page=page_obj,
            di_field_value=di_val,
            is_invoice=(document.doc_type == "invoice"),
            was_cleaned=cleanup_meta.was_cleaned(fname),
            parse_failed=cleanup_meta.parse_failed(fname),
            has_arithmetic_mismatch=cleanup_meta.has_arithmetic_mismatch(fname),
        )

        val_msg = val_result.field_errors.get(fname)
        if val_msg:
            status = "validation_failed"
        elif conf < Decimal("0.80"):
            status = "needs_review"
        else:
            status = "ok"

        field_row = ExtractedField(
            id=uuid.uuid4(),
            extraction_id=extraction.id,
            name=fname,
            value_raw=fval.value,
            value_norm={"value": fval.value} if fval.value is not None else None,
            confidence=conf,
            page=page_num,
            bbox=bbox,
            status=status,
            validation_msg=val_msg,
        )
        session.add(field_row)

    # 9. Create ExtractedLine rows
    for item in extraction_result.lines:
        line_page_num = item.page or 1
        line_page_obj = None
        if ocr_result.pages and len(ocr_result.pages) >= line_page_num:
            line_page_obj = ocr_result.pages[line_page_num - 1]
        elif ocr_result.pages:
            line_page_obj = ocr_result.pages[0]

        line_prefix = f"lines[{item.line_no - 1}]"
        conf, bbox = calculate_field_confidence(
            field_name="line_total",
            raw_value=item.line_total,
            source_text=item.source_text,
            page=line_page_obj,
            is_invoice=(document.doc_type == "invoice"),
            was_cleaned=cleanup_meta.was_cleaned(f"{line_prefix}.line_total"),
            parse_failed=cleanup_meta.parse_failed(f"{line_prefix}.line_total"),
            has_arithmetic_mismatch=cleanup_meta.has_arithmetic_mismatch(
                f"{line_prefix}.line_total"
            ),
        )

        line_val_msg = val_result.line_errors.get(item.line_no)
        if line_val_msg:
            line_status = "validation_failed"
        elif conf < Decimal("0.80"):
            line_status = "needs_review"
        else:
            line_status = "ok"

        line_row = ExtractedLine(
            id=uuid.uuid4(),
            extraction_id=extraction.id,
            line_no=item.line_no,
            item_code=item.item_code,
            description=item.description,
            qty=parse_decimal(item.qty),
            uom=item.uom,
            unit_price=parse_decimal(item.unit_price),
            discount=parse_decimal(item.discount),
            vat_rate=parse_decimal(item.vat_rate),
            line_total=parse_decimal(item.line_total),
            confidence=conf,
            page=line_page_num,
            bbox=bbox,
            status=line_status,
        )
        session.add(line_row)

    # 10. Update document status and audit
    document.status = "needs_review"

    record_audit(
        session=session,
        actor=None,
        action="document.extracted",
        entity_type="document",
        entity_id=document.id,
        ai_model=llm_model,
        prompt_version=prompt_version,
        after={
            "extraction_id": str(extraction.id),
            "version": version,
            "fields_count": len(extraction_result.header),
            "lines_count": len(extraction_result.lines),
            "suspicious": document.suspicious,
            "duplicate_of": str(document.duplicate_of) if document.duplicate_of else None,
            "est_cost_aed": str(est_cost),
        },
    )

    session.flush()
    return extraction
