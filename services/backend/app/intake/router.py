"""Router for email intake endpoint per R13 spec and Design 7.2-7.4."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record as record_audit
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import ProblemException
from app.core.middleware import get_current_request_id
from app.core.models import Document, Job
from app.core.policy import Principal
from app.documents.file_checks import validate_file
from app.documents.storage import get_storage
from app.intake.metadata import EmailMetadata, is_sender_allowed, parse_received_at
from app.intake.rate_limit import check_intake_rate_limit
from app.intake.security import get_intake_principal

router = APIRouter(prefix="/intake", tags=["intake"])


@router.post("/email", status_code=status.HTTP_202_ACCEPTED)
async def intake_email(
    file: UploadFile = File(...),
    sender: str = Form(...),
    subject: str = Form(...),
    received_at: str = Form(...),
    message_id: str = Form(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_intake_principal),
) -> dict[str, Any]:
    """Process email attachment intake with security checks and queuing."""
    # 1. Sender allowlist check
    if not is_sender_allowed(sender, settings.INTAKE_SENDER_ALLOWLIST):
        raise ProblemException(
            status_code=403,
            code="SENDER_NOT_ALLOWED",
            title="Forbidden",
            detail=f"Sender '{sender}' is not permitted by the intake allowlist",
        )

    # 2. Per-sender rate limit
    check_intake_rate_limit(sender)

    # 3. Parse timestamp
    parsed_received_at = parse_received_at(received_at)

    # 4. Read and validate file bytes
    file_bytes = await file.read()
    try:
        validation = validate_file(file_bytes)
    except ProblemException as exc:
        if exc.code == "INVALID_FILE_TYPE":
            raise ProblemException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                code="UNSUPPORTED_MEDIA_TYPE",
                title="Unsupported Media Type",
                detail=exc.detail,
            )
        raise

    # 5. SHA-256 duplicate check
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

    # 6. Upload file to private storage container
    blob_name = f"{uuid.uuid4()}{validation.extension}"
    storage = get_storage()
    storage.upload(blob_name, file_bytes, content_type=validation.mime_type)

    # 7. Create Document record
    meta = EmailMetadata(
        sender=sender,
        subject=subject,
        received_at=parsed_received_at,
        message_id=message_id,
    )
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        owner_id=principal.id,
        department_id=None,
        pr_id=None,
        po_id=None,
        vendor_id=None,
        doc_type="other",
        status="queued",
        file_sha256=validation.sha256_hash,
        blob_path=blob_name,
        mime=validation.mime_type,
        pages=validation.pages,
        size_bytes=validation.size_bytes,
        source="email",
        source_url=meta.to_source_url(),
        suspicious=False,
        created_by=principal.id,
    )
    db.add(doc)

    # 8. Enqueue normal extraction job
    job = Job(
        id=uuid.uuid4(),
        type="extract",
        payload={"document_id": str(doc.id), "request_id": get_current_request_id()},
        status="queued",
    )
    db.add(job)

    # 9. Audit entry document.received_by_email
    record_audit(
        session=db,
        actor=principal,
        action="document.received_by_email",
        entity_type="document",
        entity_id=doc.id,
        after={
            "sender": sender,
            "subject": subject,
            "received_at": parsed_received_at.isoformat(),
            "message_id": message_id,
            "filename": file.filename,
            "size_bytes": doc.size_bytes,
            "pages": doc.pages,
            "file_sha256": doc.file_sha256,
            "source": "email",
        },
    )
    db.commit()

    return {"id": doc.id, "status": doc.status}
