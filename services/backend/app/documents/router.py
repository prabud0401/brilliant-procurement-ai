"""Documents upload, listing, download, and management router per design 5.4, 7.2, 7.4."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record as record_audit
from app.core.database import get_db
from app.core.errors import ProblemException
from app.core.middleware import get_current_request_id
from app.core.models import Document, Job
from app.core.policy import Principal, get_current_principal
from app.documents.file_checks import validate_file
from app.documents.rate_limit import check_upload_rate_limit
from app.documents.storage import get_storage

router = APIRouter(prefix="/documents", tags=["documents"])

VALID_DOC_TYPES = {"quote", "purchase_order", "delivery_note", "invoice", "other"}


class DocumentResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    department_id: uuid.UUID | None
    pr_id: uuid.UUID | None
    po_id: uuid.UUID | None
    vendor_id: uuid.UUID | None
    doc_type: str
    status: str
    file_sha256: str
    mime: str
    pages: int
    size_bytes: int
    source: str
    duplicate_of: uuid.UUID | None
    duplicate_cleared_reason: str | None
    suspicious: bool
    suspicious_ack_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentSummary(BaseModel):
    id: uuid.UUID
    doc_type: str
    status: str
    pages: int
    size_bytes: int
    created_at: datetime
    duplicate_of: uuid.UUID | None
    suspicious: bool


class DocumentPatchRequest(BaseModel):
    doc_type: str | None = None
    pr_id: uuid.UUID | None = None
    po_id: uuid.UUID | None = None


def _check_doc_scope(doc: Document, principal: Principal) -> None:
    """Check if the user is allowed to access the document; return 404 if not."""
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


def _check_upload_role(principal: Principal) -> None:
    """Requester and Buyer can upload."""
    if "requester" not in principal.roles and "buyer" not in principal.roles:
        raise ProblemException(
            status_code=403,
            code="INSUFFICIENT_PERMISSIONS",
            title="Forbidden",
            detail="Only Requesters and Buyers may upload documents",
        )


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str | None = Form(None),
    pr_id: uuid.UUID | None = Form(None),
    po_id: uuid.UUID | None = Form(None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Upload a new document (multipart/form-data) per design 3.1, 7.4, US-01."""
    _check_upload_role(principal)
    check_upload_rate_limit(principal.id)

    if doc_type and doc_type not in VALID_DOC_TYPES:
        raise ProblemException(
            status_code=400,
            code="INVALID_DOC_TYPE",
            title="Invalid Document Type",
            detail=f"doc_type must be one of: {', '.join(sorted(VALID_DOC_TYPES))}",
        )

    file_bytes = await file.read()
    validation = validate_file(file_bytes)

    # SHA-256 exact-duplicate check
    existing = db.execute(
        select(Document).where(Document.file_sha256 == validation.sha256_hash)
    ).scalar_one_or_none()
    if existing:
        raise ProblemException(
            status_code=status.HTTP_409_CONFLICT,
            code="EXACT_DUPLICATE",
            title="Exact Duplicate Document",
            detail=f"Exact duplicate of existing document {existing.id}",
            errors=[{"existing_document_id": str(existing.id)}],
        )

    # Generate random blob path in private storage container
    blob_name = f"{uuid.uuid4()}{validation.extension}"
    storage = get_storage()
    storage.upload(blob_name, file_bytes, content_type=validation.mime_type)

    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        owner_id=principal.id,
        department_id=principal.department_id,
        pr_id=pr_id,
        po_id=po_id,
        vendor_id=None,
        doc_type=doc_type or "other",
        status="queued",
        file_sha256=validation.sha256_hash,
        blob_path=blob_name,
        mime=validation.mime_type,
        pages=validation.pages,
        size_bytes=validation.size_bytes,
        source="upload",
        suspicious=False,
        created_by=principal.id,
    )
    db.add(doc)

    job = Job(
        id=uuid.uuid4(),
        type="extract",
        payload={"document_id": str(doc.id), "request_id": get_current_request_id()},
        status="queued",
    )
    db.add(job)

    record_audit(
        session=db,
        actor=principal,
        action="document.uploaded",
        entity_type="document",
        entity_id=doc.id,
        after={
            "doc_type": doc.doc_type,
            "filename": file.filename,
            "size_bytes": doc.size_bytes,
            "pages": doc.pages,
            "file_sha256": doc.file_sha256,
        },
    )
    db.commit()

    return {"id": doc.id, "status": doc.status}


@router.get("", response_model=list[DocumentSummary])
def list_documents(
    doc_status: str | None = Query(None, alias="status"),
    doc_type: str | None = Query(None),
    vendor_id: uuid.UUID | None = Query(None),
    pr_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[DocumentSummary]:
    """List documents with filters and RBAC scope applied in SQL (design 5.4, 7.2)."""
    stmt = select(Document)

    # RBAC scope filtering
    if "admin" in principal.roles or "buyer" in principal.roles:
        pass  # sees all
    elif "manager" in principal.roles:
        stmt = stmt.where(Document.department_id == principal.department_id)
    elif "requester" in principal.roles:
        stmt = stmt.where(Document.owner_id == principal.id)
    else:
        return []

    if doc_status:
        stmt = stmt.where(Document.status == doc_status)
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    if vendor_id:
        stmt = stmt.where(Document.vendor_id == vendor_id)
    if pr_id:
        stmt = stmt.where(Document.pr_id == pr_id)

    stmt = stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset)
    docs = db.execute(stmt).scalars().all()

    return [
        DocumentSummary(
            id=d.id,
            doc_type=d.doc_type,
            status=d.status,
            pages=d.pages,
            size_bytes=d.size_bytes,
            created_at=d.created_at,
            duplicate_of=d.duplicate_of,
            suspicious=d.suspicious,
        )
        for d in docs
    ]


@router.get("/{id}", response_model=DocumentResponse)
def get_document(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> DocumentResponse:
    """Get metadata for a single document (design 5.4, 7.2)."""
    doc = db.execute(select(Document).where(Document.id == id)).scalar_one_or_none()
    if not doc:
        raise ProblemException(
            status_code=404,
            code="DOCUMENT_NOT_FOUND",
            title="Document Not Found",
            detail=f"Document {id} not found",
        )
    _check_doc_scope(doc, principal)

    return DocumentResponse(
        id=doc.id,
        owner_id=doc.owner_id,
        department_id=doc.department_id,
        pr_id=doc.pr_id,
        po_id=doc.po_id,
        vendor_id=doc.vendor_id,
        doc_type=doc.doc_type,
        status=doc.status,
        file_sha256=doc.file_sha256,
        mime=doc.mime,
        pages=doc.pages,
        size_bytes=doc.size_bytes,
        source=doc.source,
        duplicate_of=doc.duplicate_of,
        duplicate_cleared_reason=doc.duplicate_cleared_reason,
        suspicious=doc.suspicious,
        suspicious_ack_reason=doc.suspicious_ack_reason,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get("/{id}/file")
def get_document_file(
    id: uuid.UUID,
    page: int | None = Query(None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Response:
    """Download document file streamed with Content-Disposition and nosniff headers."""
    doc = db.execute(select(Document).where(Document.id == id)).scalar_one_or_none()
    if not doc:
        raise ProblemException(
            status_code=404,
            code="DOCUMENT_NOT_FOUND",
            title="Document Not Found",
            detail=f"Document {id} not found",
        )
    _check_doc_scope(doc, principal)

    storage = get_storage()
    file_bytes = storage.download(doc.blob_path)

    # Determine extension
    ext = ".pdf"
    if doc.mime == "image/png":
        ext = ".png"
    elif doc.mime in ("image/jpeg", "image/jpg"):
        ext = ".jpg"
    elif doc.mime == "image/tiff":
        ext = ".tiff"

    headers = {
        "Content-Disposition": f'inline; filename="{doc.id}{ext}"',
        "X-Content-Type-Options": "nosniff",
    }
    return Response(content=file_bytes, media_type=doc.mime, headers=headers)


@router.patch("/{id}", status_code=status.HTTP_202_ACCEPTED)
def patch_document(
    id: uuid.UUID,
    req: DocumentPatchRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """PATCH document: update doc_type and re-queue extraction (design 5.4, US-01)."""
    _check_upload_role(principal)
    doc = db.execute(select(Document).where(Document.id == id)).scalar_one_or_none()
    if not doc:
        raise ProblemException(
            status_code=404,
            code="DOCUMENT_NOT_FOUND",
            title="Document Not Found",
            detail=f"Document {id} not found",
        )
    _check_doc_scope(doc, principal)

    before_dict: dict[str, Any] = {}
    after_dict: dict[str, Any] = {}

    if req.doc_type is not None:
        if req.doc_type not in VALID_DOC_TYPES:
            raise ProblemException(
                status_code=400,
                code="INVALID_DOC_TYPE",
                title="Invalid Document Type",
                detail=f"doc_type must be one of: {', '.join(sorted(VALID_DOC_TYPES))}",
            )
        before_dict["doc_type"] = doc.doc_type
        doc.doc_type = req.doc_type
        doc.status = "queued"
        doc.updated_at = datetime.now(timezone.utc)
        after_dict["doc_type"] = doc.doc_type
        after_dict["status"] = "queued"

        # Enqueue new extract job
        job = Job(
            id=uuid.uuid4(),
            type="extract",
            payload={"document_id": str(doc.id)},
            status="queued",
        )
        db.add(job)

    if req.pr_id is not None:
        before_dict["pr_id"] = str(doc.pr_id) if doc.pr_id else None
        doc.pr_id = req.pr_id
        after_dict["pr_id"] = str(req.pr_id)

    if req.po_id is not None:
        before_dict["po_id"] = str(doc.po_id) if doc.po_id else None
        doc.po_id = req.po_id
        after_dict["po_id"] = str(req.po_id)

    record_audit(
        session=db,
        actor=principal,
        action="document.type_changed" if req.doc_type else "document.updated",
        entity_type="document",
        entity_id=doc.id,
        before=before_dict,
        after=after_dict,
    )
    db.commit()

    return {"id": doc.id, "status": doc.status, "doc_type": doc.doc_type}


@router.post("/{id}/extract", status_code=status.HTTP_202_ACCEPTED)
def retry_document_extract(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Re-run extraction after failure (design 5.4, NFR-REL-03)."""
    _check_upload_role(principal)
    doc = db.execute(select(Document).where(Document.id == id)).scalar_one_or_none()
    if not doc:
        raise ProblemException(
            status_code=404,
            code="DOCUMENT_NOT_FOUND",
            title="Document Not Found",
            detail=f"Document {id} not found",
        )
    _check_doc_scope(doc, principal)

    doc.status = "queued"
    doc.updated_at = datetime.now(timezone.utc)

    job = Job(
        id=uuid.uuid4(),
        type="extract",
        payload={"document_id": str(doc.id), "request_id": get_current_request_id()},
        status="queued",
    )
    db.add(job)

    record_audit(
        session=db,
        actor=principal,
        action="document.extract_requested",
        entity_type="document",
        entity_id=doc.id,
        after={"status": "queued"},
    )
    db.commit()

    return {"id": doc.id, "status": doc.status}
