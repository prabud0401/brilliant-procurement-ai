"""Integration tests for auto-classification of untyped documents and email-intake documents (F04).

Uses the mock provider to verify end-to-end classification.
"""

from __future__ import annotations

import io
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai.factory import set_document_analyzer, set_llm_client
from app.ai.providers.mock import MockDocumentAnalyzer, MockLlmClient
from app.core.bootstrap import bootstrap
from app.core.config import settings
from app.core.models import AuditLog, Document, User
from app.core.security import create_access_token
from app.documents.storage import InMemoryBlobStorage, set_storage
from app.intake.keygen import generate_key_and_hash
from app.intake.rate_limit import reset_intake_rate_limits
from app.main import app
from app.worker_main import process_single_job
from tools.datagen.layouts import render_pdf_to_bytes
from tools.datagen.scenarios import get_all_scenarios

ALL_SCENARIOS = {s.doc_id: s for s in get_all_scenarios()}


@pytest.fixture(autouse=True)
def setup_storage_and_bootstrap(
    db_session: Session, migrator_url: str
) -> Generator[None, None, None]:
    storage = InMemoryBlobStorage()
    set_storage(storage)
    set_document_analyzer(MockDocumentAnalyzer())
    set_llm_client(MockLlmClient())
    reset_intake_rate_limits()

    from seed.load import run_seed

    run_seed(db_url=migrator_url)
    test_password = "".join(["D", "e", "m", "o", "1", "2", "3", "!", "@", "#"])
    bootstrap(db_session, password=test_password, include_intake=True)

    db_session.execute(text("DELETE FROM extracted_lines"))
    db_session.execute(text("DELETE FROM extracted_fields"))
    db_session.execute(text("DELETE FROM extractions"))
    db_session.execute(text("DELETE FROM injection_flags"))
    db_session.execute(text("DELETE FROM jobs"))
    db_session.execute(text("DELETE FROM documents"))
    db_session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_no_truncate"))
    db_session.execute(text("TRUNCATE audit_log RESTART IDENTITY"))
    db_session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_no_truncate"))
    db_session.commit()

    try:
        yield
    finally:
        db_session.execute(text("DELETE FROM extracted_lines"))
        db_session.execute(text("DELETE FROM extracted_fields"))
        db_session.execute(text("DELETE FROM extractions"))
        db_session.execute(text("DELETE FROM injection_flags"))
        db_session.execute(text("DELETE FROM jobs"))
        db_session.execute(text("DELETE FROM documents"))
        db_session.commit()


def get_buyer_token(db_session: Session) -> str:
    user = db_session.execute(
        select(User).where(User.email == "buyer1@demo-holdings.example")
    ).scalar_one()
    token, _ = create_access_token(
        user_id=user.id,
        email=user.email,
        roles=[r.role for r in user.roles],
        department_id=user.department_id,
        approval_limit_aed=user.approval_limit_aed,
    )
    return token


@pytest.mark.integration
def test_upload_without_doc_type_auto_classifies_invoice(db_session: Session) -> None:
    """Upload of a generated invoice PDF without doc_type must end doc_type='invoice'."""
    client = TestClient(app)
    buyer_token = get_buyer_token(db_session)
    headers = {"Authorization": f"Bearer {buyer_token}"}

    # Render scenario S1 invoice PDF (INV-2291)
    s1_inv_spec = ALL_SCENARIOS["s1-inv-2291"]
    pdf_bytes = render_pdf_to_bytes(s1_inv_spec)

    # Upload without doc_type
    files = {"file": ("s1-inv-2291.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    resp_upload = client.post(
        "/api/v1/documents",
        data={},  # No doc_type provided
        files=files,
        headers=headers,
    )
    assert resp_upload.status_code == 202
    doc_id = uuid.UUID(resp_upload.json()["id"])

    # Initial state: doc_type defaults to "other" upon upload
    db_session.expire_all()
    doc_before = db_session.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    assert doc_before.doc_type == "other"
    assert doc_before.status == "queued"

    # Background worker processes the extraction job
    job_processed = process_single_job(db_session)
    assert job_processed is True

    # Document should now be classified as 'invoice'
    db_session.expire_all()
    doc_after = db_session.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    assert doc_after.doc_type == "invoice"
    assert doc_after.status == "needs_review"

    # Verify audit log recorded document.classified
    classified_entry = db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_id == doc_id,
            AuditLog.action == "document.classified",
        )
    ).scalar_one_or_none()
    assert classified_entry is not None
    assert classified_entry.before == {"doc_type": "other"}
    assert classified_entry.after == {"doc_type": "invoice"}


@pytest.mark.integration
def test_email_intake_auto_classifies_invoice(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Email intake of an invoice PDF must auto-classify document to doc_type='invoice'."""
    client = TestClient(app)
    plain_key, key_hash = generate_key_and_hash()
    monkeypatch.setattr(settings, "INTAKE_KEY_HASH", key_hash)
    monkeypatch.setattr(settings, "INTAKE_SENDER_ALLOWLIST", "")

    # Render scenario S1 invoice PDF
    s1_inv_spec = ALL_SCENARIOS["s1-inv-2291"]
    pdf_bytes = render_pdf_to_bytes(s1_inv_spec)

    upload_data = {
        "sender": "Gulf Line Billing <billing@gulfline.example>",
        "subject": "Tax Invoice INV-2291 for PO-0042",
        "received_at": "2026-11-20T11:00:00Z",
        "message_id": "<inv-2291@gulfline.example>",
    }
    upload_files = {"file": ("inv-2291.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    resp = client.post(
        "/api/v1/intake/email",
        data=upload_data,
        files=upload_files,
        headers={"X-Intake-Key": plain_key},
    )
    assert resp.status_code == 202
    doc_id = uuid.UUID(resp.json()["id"])

    # Initial state from email intake is doc_type="other"
    db_session.expire_all()
    doc_before = db_session.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    assert doc_before.doc_type == "other"
    assert doc_before.source == "email"

    # Background worker processes the extraction job
    job_processed = process_single_job(db_session)
    assert job_processed is True

    # Document should now be classified as 'invoice'
    db_session.expire_all()
    doc_after = db_session.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    assert doc_after.doc_type == "invoice"
    assert doc_after.status == "needs_review"

    # Verify audit log recorded document.classified
    classified_entry = db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_id == doc_id,
            AuditLog.action == "document.classified",
        )
    ).scalar_one_or_none()
    assert classified_entry is not None
    assert classified_entry.before == {"doc_type": "other"}
    assert classified_entry.after == {"doc_type": "invoice"}
