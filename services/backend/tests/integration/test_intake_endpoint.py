"""Integration tests for email intake endpoint: auth, validation, extraction, queue."""

from __future__ import annotations

import io
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai.factory import set_document_analyzer, set_llm_client
from app.ai.providers.replay import ReplayDocumentAnalyzer, ReplayLlmClient
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
    set_document_analyzer(ReplayDocumentAnalyzer())
    set_llm_client(ReplayLlmClient())
    reset_intake_rate_limits()

    from seed.load import run_seed

    run_seed(db_url=migrator_url)
    test_password = "".join(["D", "e", "m", "o", "1", "2", "3", "!", "@", "#"])
    bootstrap(db_session, password=test_password)

    # Clean existing document, job, and audit state
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
def test_valid_key_and_pdf_enqueues_and_extracts(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    plain_key, key_hash = generate_key_and_hash()
    monkeypatch.setattr(settings, "INTAKE_KEY_HASH", key_hash)
    monkeypatch.setattr(settings, "INTAKE_SENDER_ALLOWLIST", "")

    # Generate scenario S1 quote PDF
    s1_spec = ALL_SCENARIOS["s1-quote-gulfline"]
    pdf_bytes = render_pdf_to_bytes(s1_spec)

    upload_data = {
        "sender": "Gulf Line Sales <sales@gulfline.example>",
        "subject": "Quotation for IT Hardware Q-2026-101",
        "received_at": "2026-11-20T10:00:00Z",
        "message_id": "<gulf-q101@gulfline.example>",
    }
    upload_files = {"file": ("quote-gulfline.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    # 1. Post to intake endpoint
    resp = client.post(
        "/api/v1/intake/email",
        data=upload_data,
        files=upload_files,
        headers={"X-Intake-Key": plain_key},
    )
    assert resp.status_code == 202
    res_json = resp.json()
    assert "id" in res_json
    assert res_json["status"] == "queued"
    doc_id = uuid.UUID(res_json["id"])

    # 2. Verify Document in DB
    db_session.expire_all()
    doc = db_session.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    assert doc.source == "email"
    assert doc.status == "queued"
    assert "sales@gulfline.example" in (doc.source_url or "")

    # 3. Verify audit log entry document.received_by_email
    audit_entry = db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_id == doc_id,
            AuditLog.action == "document.received_by_email",
        )
    ).scalar_one()
    assert audit_entry.after is not None
    assert audit_entry.after["sender"] == upload_data["sender"]
    assert audit_entry.after["subject"] == upload_data["subject"]
    assert audit_entry.after["received_at"] == "2026-11-20T10:00:00+00:00"
    assert audit_entry.after["source"] == "email"

    # 4. Process extraction job through background worker
    job_processed = process_single_job(db_session)
    assert job_processed is True

    db_session.expire_all()
    doc_after = db_session.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    assert doc_after.status in ("needs_review", "confirmed")

    # 5. Verify document is present in Buyer queue
    buyer_token = get_buyer_token(db_session)
    buyer_resp = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert buyer_resp.status_code == 200
    docs = buyer_resp.json()
    matching = [d for d in docs if d["id"] == str(doc_id)]
    assert len(matching) == 1


@pytest.mark.integration
def test_unsupported_file_type_returns_415(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    plain_key, key_hash = generate_key_and_hash()
    monkeypatch.setattr(settings, "INTAKE_KEY_HASH", key_hash)

    exe_bytes = b"MZ\x90\x00\x03\x00\x00\x00executable-content"
    resp = client.post(
        "/api/v1/intake/email",
        data={
            "sender": "supplier@example.com",
            "subject": "Malicious payload",
            "received_at": "2026-11-20T10:00:00Z",
            "message_id": "<malicious-1@example.com>",
        },
        files={"file": ("malware.exe", io.BytesIO(exe_bytes), "application/octet-stream")},
        headers={"X-Intake-Key": plain_key},
    )
    assert resp.status_code == 415


@pytest.mark.integration
def test_oversized_file_returns_413(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    plain_key, key_hash = generate_key_and_hash()
    monkeypatch.setattr(settings, "INTAKE_KEY_HASH", key_hash)
    # Set limit low for fast testing
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 100)

    # 200 bytes PDF
    big_pdf = b"%PDF-1.4 " + b"X" * 200
    resp = client.post(
        "/api/v1/intake/email",
        data={
            "sender": "supplier@example.com",
            "subject": "Large file",
            "received_at": "2026-11-20T10:00:00Z",
            "message_id": "<large-1@example.com>",
        },
        files={"file": ("big.pdf", io.BytesIO(big_pdf), "application/pdf")},
        headers={"X-Intake-Key": plain_key},
    )
    assert resp.status_code == 413


@pytest.mark.integration
def test_corrupt_pdf_returns_400(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    plain_key, key_hash = generate_key_and_hash()
    monkeypatch.setattr(settings, "INTAKE_KEY_HASH", key_hash)

    corrupt_pdf = b"%PDF-1.4 corrupt broken non-parsable content without xref or trailer"
    resp = client.post(
        "/api/v1/intake/email",
        data={
            "sender": "supplier@example.com",
            "subject": "Corrupt file",
            "received_at": "2026-11-20T10:00:00Z",
            "message_id": "<corrupt-1@example.com>",
        },
        files={"file": ("corrupt.pdf", io.BytesIO(corrupt_pdf), "application/pdf")},
        headers={"X-Intake-Key": plain_key},
    )
    assert resp.status_code == 400


@pytest.mark.integration
def test_duplicate_file_returns_409(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    plain_key, key_hash = generate_key_and_hash()
    monkeypatch.setattr(settings, "INTAKE_KEY_HASH", key_hash)

    s1_spec = ALL_SCENARIOS["s1-quote-gulfline"]
    pdf_bytes = render_pdf_to_bytes(s1_spec)

    payload = {
        "sender": "sales@gulfline.example",
        "subject": "Quote 1",
        "received_at": "2026-11-20T10:00:00Z",
        "message_id": "<msg-dup-1@gulfline.example>",
    }

    # First intake succeeds
    resp1 = client.post(
        "/api/v1/intake/email",
        data=payload,
        files={"file": ("quote1.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers={"X-Intake-Key": plain_key},
    )
    assert resp1.status_code == 202

    # Second intake with same PDF bytes triggers exact duplicate 409
    payload["message_id"] = "<msg-dup-2@gulfline.example>"
    resp2 = client.post(
        "/api/v1/intake/email",
        data=payload,
        files={"file": ("quote2.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers={"X-Intake-Key": plain_key},
    )
    assert resp2.status_code == 409


@pytest.mark.integration
def test_missing_or_wrong_key_returns_401(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    plain_key, key_hash = generate_key_and_hash()
    monkeypatch.setattr(settings, "INTAKE_KEY_HASH", key_hash)

    pdf_bytes = b"%PDF-1.4 sample data"

    # 1. Missing key
    resp_missing = client.post(
        "/api/v1/intake/email",
        data={
            "sender": "sales@supplier.example",
            "subject": "Missing key",
            "received_at": "2026-11-20T10:00:00Z",
            "message_id": "<no-key@supplier.example>",
        },
        files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp_missing.status_code == 401

    # 2. Wrong key
    resp_wrong = client.post(
        "/api/v1/intake/email",
        data={
            "sender": "sales@supplier.example",
            "subject": "Wrong key",
            "received_at": "2026-11-20T10:00:00Z",
            "message_id": "<wrong-key@supplier.example>",
        },
        files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers={"X-Intake-Key": "incorrect-api-key-value"},
    )
    assert resp_wrong.status_code == 401


@pytest.mark.integration
def test_sender_not_in_allowlist_returns_403(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    plain_key, key_hash = generate_key_and_hash()
    monkeypatch.setattr(settings, "INTAKE_KEY_HASH", key_hash)
    monkeypatch.setattr(settings, "INTAKE_SENDER_ALLOWLIST", "allowed@supplier.example")

    pdf_bytes = b"%PDF-1.4 sample data"
    resp = client.post(
        "/api/v1/intake/email",
        data={
            "sender": "forbidden@attacker.example",
            "subject": "Quote from unknown vendor",
            "received_at": "2026-11-20T10:00:00Z",
            "message_id": "<forbidden@attacker.example>",
        },
        files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers={"X-Intake-Key": plain_key},
    )
    assert resp.status_code == 403
