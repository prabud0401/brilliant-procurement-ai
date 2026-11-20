"""Security tests for email intake: isolation, key rejection, role boundaries, redaction."""

from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.core.models import Document, User
from app.core.policy import Principal, get_current_principal
from app.documents.storage import InMemoryBlobStorage, set_storage
from app.intake.keygen import generate_key_and_hash
from app.main import app


@pytest.mark.security
def test_intake_key_refused_on_other_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    plain_key, key_hash = generate_key_and_hash()
    monkeypatch.setattr(settings, "INTAKE_KEY_HASH", key_hash)

    headers = {"X-Intake-Key": plain_key}

    # 1. Calling documents endpoint with intake key returns 401
    resp_docs = client.get("/api/v1/documents", headers=headers)
    assert resp_docs.status_code == 401

    # 2. Calling health endpoint with intake key returns 401
    resp_health = client.get("/healthz", headers=headers)
    assert resp_health.status_code == 401

    # 3. Calling audit endpoint with intake key returns 401
    resp_audit = client.get("/api/v1/audit", headers=headers)
    assert resp_audit.status_code == 401


@pytest.mark.security
def test_intake_role_cannot_list_or_read_documents() -> None:
    intake_principal = Principal(
        id=uuid.uuid4(),
        email="intake@demo-holdings.example",
        display_name="Intake Service Account",
        roles=["intake"],
        department_id=None,
        department_name=None,
        approval_limit_aed=Decimal("0.00"),
        is_demo=True,
        active=True,
    )

    now = datetime.now(timezone.utc)
    sample_doc = Document(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        doc_type="quote",
        status="needs_review",
        file_sha256="dummy-sha",
        blob_path="dummy.pdf",
        mime="application/pdf",
        pages=1,
        size_bytes=100,
        source="upload",
        suspicious=False,
        created_at=now,
        updated_at=now,
    )

    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_doc]
    mock_db.execute.return_value.scalar_one_or_none.return_value = sample_doc

    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_principal] = lambda: intake_principal

    try:
        # 1. Intake role listing documents returns empty list (SQL scope returns [])
        resp_list = client.get("/api/v1/documents")
        assert resp_list.status_code == 200
        assert resp_list.json() == []

        # 2. Intake role getting specific document returns 404 (scope check fails)
        resp_get = client.get(f"/api/v1/documents/{sample_doc.id}")
        assert resp_get.status_code == 404
        assert resp_get.json()["code"] == "DOCUMENT_NOT_FOUND"

        # 3. Intake role cannot upload via standard document upload (returns 403)
        resp_upload = client.post(
            "/api/v1/documents",
            data={"doc_type": "quote"},
            files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 sample"), "application/pdf")},
        )
        assert resp_upload.status_code == 403
        assert resp_upload.json()["code"] == "INSUFFICIENT_PERMISSIONS"

        # 4. Intake role cannot access purchase requests (returns 403)
        resp_pr = client.post(
            "/api/v1/purchase-requests",
            json={"title": "Test PR", "items": []},
        )
        assert resp_pr.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.security
def test_intake_service_account_cannot_login_with_password() -> None:
    intake_user = User(
        id=uuid.uuid4(),
        email="intake@demo-holdings.example",
        display_name="Intake Service Account",
        approval_limit_aed=Decimal("0.00"),
        is_demo=True,
        active=True,
        password_hash=None,  # No password set for service accounts
    )

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = intake_user

    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "intake@demo-holdings.example", "password": "AnyPassword123!"},
        )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


@pytest.mark.security
def test_intake_key_never_logged_or_returned_in_responses(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    storage = InMemoryBlobStorage()
    set_storage(storage)

    plain_key, key_hash = generate_key_and_hash()
    monkeypatch.setattr(settings, "INTAKE_KEY_HASH", key_hash)

    intake_user = User(
        id=uuid.uuid4(),
        email="intake@demo-holdings.example",
        display_name="Intake Service Account",
        approval_limit_aed=Decimal("0.00"),
        is_demo=True,
        active=True,
        password_hash=None,
    )

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = intake_user
    mock_db.execute.return_value.scalar_one_or_none.return_value = None  # No duplicates

    caplog.set_level(logging.DEBUG)

    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        # Valid PNG file bytes (supported MIME type without PDF structure requirements)
        file_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 30
        resp = client.post(
            "/api/v1/intake/email",
            data={
                "sender": "supplier@example.com",
                "subject": "Quote test",
                "received_at": "2026-11-20T10:00:00Z",
                "message_id": "<test-secret@supplier.example>",
            },
            files={"file": ("quote.png", io.BytesIO(file_bytes), "image/png")},
            headers={"X-Intake-Key": plain_key},
        )

        assert resp.status_code == 202

        # Key must NOT appear in response body or headers
        assert plain_key not in resp.text
        for _, hval in resp.headers.items():
            assert plain_key not in hval

        # Key must NOT appear in any captured application logs
        for record in caplog.records:
            assert plain_key not in record.getMessage()
    finally:
        app.dependency_overrides.clear()
