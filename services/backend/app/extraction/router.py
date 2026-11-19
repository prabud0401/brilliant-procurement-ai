"""Extraction review and confirmation router per design 5.4 and US-03."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record as record_audit
from app.core.database import get_db
from app.core.errors import ProblemException
from app.core.models import Document, ExtractedField, ExtractedLine, Extraction, Vendor
from app.core.policy import Principal, get_current_principal, require

router = APIRouter(prefix="/documents", tags=["extraction"])


class FieldUpdateRequest(BaseModel):
    value: str | None = None
    confirm: bool = False


class LineUpdateRequest(BaseModel):
    item_code: str | None = None
    description: str | None = None
    qty: Decimal | None = None
    uom: str | None = None
    unit_price: Decimal | None = None
    discount: Decimal | None = None
    vat_rate: Decimal | None = None
    line_total: Decimal | None = None
    confirm: bool = False


class VendorLinkRequest(BaseModel):
    vendor_id: uuid.UUID | None = None
    new_vendor: bool = False


class NotDuplicateRequest(BaseModel):
    reason: str = Field(..., min_length=10)


class FieldResponse(BaseModel):
    id: uuid.UUID
    name: str
    value_raw: str | None
    value_norm: dict[str, Any] | None
    confidence: Decimal | None
    page: int
    bbox: dict[str, Any] | None
    status: str
    validation_msg: str | None
    confirmed_by: uuid.UUID | None
    confirmed_at: datetime | None


class LineResponse(BaseModel):
    id: uuid.UUID
    line_no: int
    item_code: str | None
    description: str | None
    qty: Decimal | None
    uom: str | None
    unit_price: Decimal | None
    discount: Decimal | None
    vat_rate: Decimal | None
    line_total: Decimal | None
    confidence: Decimal | None
    page: int
    bbox: dict[str, Any] | None
    status: str


class ExtractionResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    version: int
    di_model: str | None
    llm_model: str | None
    prompt_version: str | None
    status: str
    created_at: datetime
    fields: list[FieldResponse]
    lines: list[LineResponse]


def _check_doc_scope(doc: Document, principal: Principal) -> None:
    """Ensure user has read access to document; otherwise 404 (design 7.2)."""
    if "admin" in principal.roles or "buyer" in principal.roles:
        return
    if "manager" in principal.roles and doc.department_id == principal.department_id:
        return
    if "requester" in principal.roles and doc.owner_id == principal.id:
        return
    raise ProblemException(
        status_code=404,
        code="DOCUMENT_NOT_FOUND",
        title="Document Not Found",
        detail=f"Document {doc.id} not found",
    )


@router.get("/{id}/extraction", response_model=ExtractionResponse)
def get_document_extraction(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> ExtractionResponse:
    """Get latest extraction fields and line items for a document."""
    doc = db.execute(select(Document).where(Document.id == id)).scalar_one_or_none()
    if not doc:
        raise ProblemException(
            status_code=404,
            code="DOCUMENT_NOT_FOUND",
            title="Document Not Found",
            detail=f"Document {id} not found",
        )
    _check_doc_scope(doc, principal)

    # Get latest completed extraction
    extraction = (
        db.execute(
            select(Extraction)
            .where(Extraction.document_id == id)
            .order_by(Extraction.version.desc())
        )
        .scalars()
        .first()
    )
    if not extraction:
        raise ProblemException(
            status_code=404,
            code="EXTRACTION_NOT_FOUND",
            title="Extraction Not Found",
            detail=f"No extraction found for document {id}",
        )

    return ExtractionResponse(
        id=extraction.id,
        document_id=extraction.document_id,
        version=extraction.version,
        di_model=extraction.di_model,
        llm_model=extraction.llm_model,
        prompt_version=extraction.prompt_version,
        status=extraction.status,
        created_at=extraction.created_at,
        fields=[
            FieldResponse(
                id=f.id,
                name=f.name,
                value_raw=f.value_raw,
                value_norm=f.value_norm,
                confidence=f.confidence,
                page=f.page,
                bbox=f.bbox,
                status=f.status,
                validation_msg=f.validation_msg,
                confirmed_by=f.confirmed_by,
                confirmed_at=f.confirmed_at,
            )
            for f in extraction.fields
        ],
        lines=[
            LineResponse(
                id=line_item.id,
                line_no=line_item.line_no,
                item_code=line_item.item_code,
                description=line_item.description,
                qty=line_item.qty,
                uom=line_item.uom,
                unit_price=line_item.unit_price,
                discount=line_item.discount,
                vat_rate=line_item.vat_rate,
                line_total=line_item.line_total,
                confidence=line_item.confidence,
                page=line_item.page,
                bbox=line_item.bbox,
                status=line_item.status,
            )
            for line_item in extraction.lines
        ],
    )


@router.patch("/{id}/fields/{field_id}", response_model=FieldResponse)
def update_extracted_field(
    id: uuid.UUID,
    field_id: uuid.UUID,
    req: FieldUpdateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require("document.review")),
) -> FieldResponse:
    """Buyer corrects or confirms a flagged field (design 5.4, US-03)."""
    field = (
        db.execute(
            select(ExtractedField)
            .join(Extraction)
            .where(Extraction.document_id == id, ExtractedField.id == field_id)
        )
        .scalars()
        .one_or_none()
    )
    if not field:
        raise ProblemException(
            status_code=404,
            code="FIELD_NOT_FOUND",
            title="Field Not Found",
            detail=f"Field {field_id} not found on document {id}",
        )

    now = datetime.now(timezone.utc)
    before_dict = {
        "value_raw": field.value_raw,
        "status": field.status,
        "validation_msg": field.validation_msg,
    }

    if req.value is not None:
        field.value_raw = req.value
        field.value_norm = {"value": req.value}
        field.status = "corrected"
        field.validation_msg = None
        field.confirmed_by = principal.id
        field.confirmed_at = now
        action = "field.corrected"
    elif req.confirm:
        field.status = "confirmed"
        field.validation_msg = None
        field.confirmed_by = principal.id
        field.confirmed_at = now
        action = "field.confirmed"
    else:
        raise ProblemException(
            status_code=400,
            code="INVALID_UPDATE",
            title="Invalid Update",
            detail="Must provide either value or confirm=true",
        )

    after_dict = {
        "value_raw": field.value_raw,
        "status": field.status,
        "validation_msg": field.validation_msg,
    }

    record_audit(
        session=db,
        actor=principal,
        action=action,
        entity_type="extracted_field",
        entity_id=field.id,
        before=before_dict,
        after=after_dict,
    )
    db.commit()

    return FieldResponse(
        id=field.id,
        name=field.name,
        value_raw=field.value_raw,
        value_norm=field.value_norm,
        confidence=field.confidence,
        page=field.page,
        bbox=field.bbox,
        status=field.status,
        validation_msg=field.validation_msg,
        confirmed_by=field.confirmed_by,
        confirmed_at=field.confirmed_at,
    )


@router.patch("/{id}/lines/{line_id}", response_model=LineResponse)
def update_extracted_line(
    id: uuid.UUID,
    line_id: uuid.UUID,
    req: LineUpdateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require("document.review")),
) -> LineResponse:
    """Buyer corrects or confirms a line item (design 5.4, US-03)."""
    line = (
        db.execute(
            select(ExtractedLine)
            .join(Extraction)
            .where(Extraction.document_id == id, ExtractedLine.id == line_id)
        )
        .scalars()
        .one_or_none()
    )
    if not line:
        raise ProblemException(
            status_code=404,
            code="LINE_NOT_FOUND",
            title="Line Item Not Found",
            detail=f"Line item {line_id} not found on document {id}",
        )

    before_dict = {
        "item_code": line.item_code,
        "description": line.description,
        "qty": str(line.qty) if line.qty else None,
        "unit_price": str(line.unit_price) if line.unit_price else None,
        "line_total": str(line.line_total) if line.line_total else None,
        "status": line.status,
    }

    if req.confirm:
        line.status = "confirmed"
        action = "line.confirmed"
    else:
        if req.item_code is not None:
            line.item_code = req.item_code
        if req.description is not None:
            line.description = req.description
        if req.qty is not None:
            line.qty = req.qty
        if req.uom is not None:
            line.uom = req.uom
        if req.unit_price is not None:
            line.unit_price = req.unit_price
        if req.discount is not None:
            line.discount = req.discount
        if req.vat_rate is not None:
            line.vat_rate = req.vat_rate
        if req.line_total is not None:
            line.line_total = req.line_total

        line.status = "corrected"
        action = "line.corrected"

    after_dict = {
        "item_code": line.item_code,
        "description": line.description,
        "qty": str(line.qty) if line.qty else None,
        "unit_price": str(line.unit_price) if line.unit_price else None,
        "line_total": str(line.line_total) if line.line_total else None,
        "status": line.status,
    }

    record_audit(
        session=db,
        actor=principal,
        action=action,
        entity_type="extracted_line",
        entity_id=line.id,
        before=before_dict,
        after=after_dict,
    )
    db.commit()

    return LineResponse(
        id=line.id,
        line_no=line.line_no,
        item_code=line.item_code,
        description=line.description,
        qty=line.qty,
        uom=line.uom,
        unit_price=line.unit_price,
        discount=line.discount,
        vat_rate=line.vat_rate,
        line_total=line.line_total,
        confidence=line.confidence,
        page=line.page,
        bbox=line.bbox,
        status=line.status,
    )


@router.post("/{id}/confirm")
def confirm_document(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require("document.review")),
) -> dict[str, Any]:
    """Buyer confirms a reviewed document. Blocked if any field has open flags."""
    doc = db.execute(select(Document).where(Document.id == id)).scalar_one_or_none()
    if not doc:
        raise ProblemException(
            status_code=404,
            code="DOCUMENT_NOT_FOUND",
            title="Document Not Found",
            detail=f"Document {id} not found",
        )

    # Check for open flags in latest extraction
    latest_ext = (
        db.execute(
            select(Extraction)
            .where(Extraction.document_id == id)
            .order_by(Extraction.version.desc())
        )
        .scalars()
        .first()
    )

    open_fields = []
    if latest_ext:
        for f in latest_ext.fields:
            if f.status in ("needs_review", "validation_failed"):
                open_fields.append(
                    {
                        "id": str(f.id),
                        "name": f.name,
                        "status": f.status,
                        "message": f.validation_msg,
                    }
                )
        for line_item in latest_ext.lines:
            if line_item.status in ("needs_review", "validation_failed"):
                open_fields.append(
                    {
                        "id": str(line_item.id),
                        "name": f"line_{line_item.line_no}",
                        "status": line_item.status,
                        "message": "Line requires review",
                    }
                )

    suspicious_open = doc.suspicious and not doc.suspicious_ack_reason
    duplicate_open = bool(doc.duplicate_of and not doc.duplicate_cleared_reason)
    if open_fields or suspicious_open or duplicate_open:
        extra_errors: list[dict[str, Any]] = list(open_fields)
        if suspicious_open:
            extra_errors.append(
                {
                    "name": "suspicious",
                    "message": "Document flagged as suspicious; acknowledge it before confirming",
                }
            )
        if doc.duplicate_of and not doc.duplicate_cleared_reason:
            extra_errors.append(
                {"name": "duplicate_of", "message": f"Possible duplicate of {doc.duplicate_of}"}
            )
        raise ProblemException(
            status_code=status.HTTP_409_CONFLICT,
            code="FLAGS_OPEN",
            title="Cannot Confirm Document",
            detail=f"Document has {len(extra_errors)} open flag(s)",
            errors=extra_errors,
        )

    before_status = doc.status
    doc.status = "confirmed"
    doc.updated_at = datetime.now(timezone.utc)

    record_audit(
        session=db,
        actor=principal,
        action="document.confirmed",
        entity_type="document",
        entity_id=doc.id,
        before={"status": before_status},
        after={"status": "confirmed"},
    )
    db.commit()

    return {"id": doc.id, "status": "confirmed"}


@router.post("/{id}/vendor")
def link_document_vendor(
    id: uuid.UUID,
    req: VendorLinkRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require("document.review")),
) -> dict[str, Any]:
    """Buyer links a vendor from master data or flags new vendor (design 5.4, US-05)."""
    doc = db.execute(select(Document).where(Document.id == id)).scalar_one_or_none()
    if not doc:
        raise ProblemException(
            status_code=404,
            code="DOCUMENT_NOT_FOUND",
            title="Document Not Found",
            detail=f"Document {id} not found",
        )

    before_vendor = str(doc.vendor_id) if doc.vendor_id else None

    if req.new_vendor:
        doc.vendor_id = None
        after_vendor = None
    elif req.vendor_id:
        vendor = db.execute(select(Vendor).where(Vendor.id == req.vendor_id)).scalar_one_or_none()
        if not vendor:
            raise ProblemException(
                status_code=404,
                code="VENDOR_NOT_FOUND",
                title="Vendor Not Found",
                detail=f"Vendor {req.vendor_id} does not exist",
            )
        doc.vendor_id = vendor.id
        after_vendor = str(vendor.id)
    else:
        raise ProblemException(
            status_code=400,
            code="INVALID_REQUEST",
            title="Invalid Request",
            detail="Must specify vendor_id or new_vendor=true",
        )

    record_audit(
        session=db,
        actor=principal,
        action="document.vendor_linked",
        entity_type="document",
        entity_id=doc.id,
        before={"vendor_id": before_vendor},
        after={"vendor_id": after_vendor},
    )
    db.commit()

    return {"document_id": doc.id, "vendor_id": doc.vendor_id}


@router.post("/{id}/not-duplicate")
def clear_duplicate_flag(
    id: uuid.UUID,
    req: NotDuplicateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require("document.review")),
) -> dict[str, Any]:
    """Buyer clears a duplicate document flag with a recorded reason (design 5.4, US-06)."""
    doc = db.execute(select(Document).where(Document.id == id)).scalar_one_or_none()
    if not doc:
        raise ProblemException(
            status_code=404,
            code="DOCUMENT_NOT_FOUND",
            title="Document Not Found",
            detail=f"Document {id} not found",
        )

    clean_reason = req.reason.strip()
    if len(clean_reason) < 10:
        raise ProblemException(
            status_code=422,
            code="REASON_TOO_SHORT",
            title="Reason Too Short",
            detail="Override reason must be at least 10 characters",
        )

    before_val = doc.duplicate_cleared_reason
    doc.duplicate_cleared_reason = clean_reason

    record_audit(
        session=db,
        actor=principal,
        action="document.duplicate_cleared",
        entity_type="document",
        entity_id=doc.id,
        reason=clean_reason,
        before={"duplicate_cleared_reason": before_val},
        after={"duplicate_cleared_reason": clean_reason},
    )
    db.commit()

    return {"document_id": doc.id, "duplicate_cleared": True, "reason": clean_reason}


@router.post("/{id}/acknowledge-suspicious")
def acknowledge_suspicious(
    id: uuid.UUID,
    req: NotDuplicateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require("document.review")),
) -> dict[str, Any]:
    """Buyer acknowledges a "Suspicious content" flag with a recorded reason.

    The injection flags stay on record; the acknowledgement only lifts the confirm block
    after a person has checked the extracted values against the document (design 7.5).
    """
    doc = db.execute(select(Document).where(Document.id == id)).scalar_one_or_none()
    if not doc:
        raise ProblemException(
            status_code=404,
            code="DOCUMENT_NOT_FOUND",
            title="Document Not Found",
            detail=f"Document {id} not found",
        )
    if not doc.suspicious:
        raise ProblemException(
            status_code=409,
            code="NOT_SUSPICIOUS",
            title="Document Not Flagged",
            detail="Document is not flagged as suspicious",
        )

    clean_reason = req.reason.strip()
    if len(clean_reason) < 10:
        raise ProblemException(
            status_code=422,
            code="REASON_TOO_SHORT",
            title="Reason Too Short",
            detail="Acknowledgement reason must be at least 10 characters",
        )

    before_val = doc.suspicious_ack_reason
    doc.suspicious_ack_reason = clean_reason
    record_audit(
        session=db,
        actor=principal,
        action="injection.acknowledged",
        entity_type="document",
        entity_id=doc.id,
        reason=clean_reason,
        before={"suspicious_ack_reason": before_val},
        after={"suspicious_ack_reason": clean_reason},
    )
    db.commit()

    return {"document_id": doc.id, "suspicious_acknowledged": True, "reason": clean_reason}
