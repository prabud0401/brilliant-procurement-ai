"""Security tests for Document RBAC, scope filtering, role permissions, and injection defence."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.models import Document, ExtractedField, Extraction, InjectionFlag
from app.core.policy import Principal, get_current_principal
from app.documents.storage import InMemoryBlobStorage, set_storage
from app.extraction.service import run_extraction
from app.main import app


@pytest.fixture
def test_principals() -> dict[str, Principal]:
    dept_1 = uuid.uuid4()
    dept_2 = uuid.uuid4()
    return {
        "requester_1": Principal(
            id=uuid.uuid4(),
            email="req1@demo.example",
            display_name="Requester 1",
            roles=["requester"],
            department_id=dept_1,
            department_name="IT",
            approval_limit_aed=Decimal("0.00"),
        ),
        "requester_2": Principal(
            id=uuid.uuid4(),
            email="req2@demo.example",
            display_name="Requester 2",
            roles=["requester"],
            department_id=dept_2,
            department_name="Facilities",
            approval_limit_aed=Decimal("0.00"),
        ),
        "manager_1": Principal(
            id=uuid.uuid4(),
            email="mgr1@demo.example",
            display_name="Manager 1",
            roles=["manager"],
            department_id=dept_1,
            department_name="IT",
            approval_limit_aed=Decimal("50000.00"),
        ),
        "buyer": Principal(
            id=uuid.uuid4(),
            email="buyer@demo.example",
            display_name="Buyer",
            roles=["buyer"],
            department_id=None,
            department_name=None,
            approval_limit_aed=Decimal("0.00"),
        ),
    }


@pytest.mark.security
def test_other_users_documents_return_404(test_principals: dict[str, Principal]) -> None:
    """Design 7.2: Requester or Manager reading others' records returns 404, not 403."""
    doc_id = uuid.uuid4()
    owner_id = test_principals["requester_2"].id
    dept_id = test_principals["requester_2"].department_id
    now = datetime.now(timezone.utc)

    doc = Document(
        id=doc_id,
        owner_id=owner_id,
        department_id=dept_id,
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
    mock_db.execute.return_value.scalar_one_or_none.return_value = doc

    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        # Requester 1 tries to access Requester 2's document
        app.dependency_overrides[get_current_principal] = lambda: test_principals["requester_1"]
        resp_meta = client.get(f"/api/v1/documents/{doc_id}")
        assert resp_meta.status_code == 404
        assert resp_meta.json()["code"] == "DOCUMENT_NOT_FOUND"

        resp_file = client.get(f"/api/v1/documents/{doc_id}/file")
        assert resp_file.status_code == 404

        resp_ext = client.get(f"/api/v1/documents/{doc_id}/extraction")
        assert resp_ext.status_code == 404

        # Manager 1 (Dept 1) tries to access Dept 2's document
        app.dependency_overrides[get_current_principal] = lambda: test_principals["manager_1"]
        resp_mgr = client.get(f"/api/v1/documents/{doc_id}")
        assert resp_mgr.status_code == 404

        # Buyer can access any document
        app.dependency_overrides[get_current_principal] = lambda: test_principals["buyer"]
        resp_buyer = client.get(f"/api/v1/documents/{doc_id}")
        assert resp_buyer.status_code == 200
    finally:
        app.dependency_overrides.clear()


@pytest.mark.security
def test_requester_and_manager_cannot_confirm_403(test_principals: dict[str, Principal]) -> None:
    """Only Buyer can confirm documents or patch fields (design 7.2)."""
    doc_id = uuid.uuid4()
    field_id = uuid.uuid4()
    client = TestClient(app)

    # Requester attempt
    app.dependency_overrides[get_current_principal] = lambda: test_principals["requester_1"]
    resp_confirm = client.post(f"/api/v1/documents/{doc_id}/confirm")
    assert resp_confirm.status_code == 403
    assert resp_confirm.json()["code"] == "FORBIDDEN"

    resp_patch = client.patch(
        f"/api/v1/documents/{doc_id}/fields/{field_id}", json={"confirm": True}
    )
    assert resp_patch.status_code == 403

    # Manager attempt
    app.dependency_overrides[get_current_principal] = lambda: test_principals["manager_1"]
    resp_mgr_confirm = client.post(f"/api/v1/documents/{doc_id}/confirm")
    assert resp_mgr_confirm.status_code == 403

    resp_mgr_patch = client.patch(
        f"/api/v1/documents/{doc_id}/fields/{field_id}", json={"confirm": True}
    )
    assert resp_mgr_patch.status_code == 403
    app.dependency_overrides.clear()


@pytest.mark.security
def test_cannot_confirm_when_flags_open_409(test_principals: dict[str, Principal]) -> None:
    """Document confirmation is blocked with 409 while open flags or review statuses exist."""
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        owner_id=test_principals["buyer"].id,
        department_id=None,
        doc_type="invoice",
        status="needs_review",
        file_sha256="test-sha",
        blob_path="test.pdf",
        mime="application/pdf",
        pages=1,
        size_bytes=100,
        source="upload",
        suspicious=False,
    )

    unconfirmed_field = ExtractedField(
        id=uuid.uuid4(),
        extraction_id=uuid.uuid4(),
        name="total",
        value_raw="100.00",
        status="needs_review",  # Open flag!
        page=1,
    )
    extraction = Extraction(
        id=uuid.uuid4(),
        document_id=doc_id,
        version=1,
        status="completed",
        fields=[unconfirmed_field],
        lines=[],
    )

    mock_db = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = doc
    mock_db.execute.return_value.scalars.return_value.first.return_value = extraction

    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_principal] = lambda: test_principals["buyer"]
    try:
        resp = client.post(f"/api/v1/documents/{doc_id}/confirm")
        assert resp.status_code == 409
        data = resp.json()
        assert data["code"] == "FLAGS_OPEN"
        assert "errors" in data and len(data["errors"]) > 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.security
def test_s7_injection_invoice_flagged_and_values_unchanged() -> None:
    """Scenario S7: Prompt injection is flagged, total remains 2625.00, confirm is blocked."""
    # Use in-memory blob storage and test session
    storage = InMemoryBlobStorage()
    set_storage(storage)

    # Set up dummy PDF bytes
    doc_bytes = b"%PDF-1.4 sample injection invoice"
    blob_path = "s7-invoice.pdf"
    storage.upload(blob_path, doc_bytes, "application/pdf")

    # Mock DB session
    session = MagicMock()
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        owner_id=uuid.uuid4(),
        department_id=None,
        doc_type="invoice",
        status="queued",
        file_sha256="s7-sha256",
        blob_path=blob_path,
        mime="application/pdf",
        pages=1,
        size_bytes=len(doc_bytes),
        source="upload",
        suspicious=False,
    )

    def mock_execute(*args: Any, **kwargs: Any) -> MagicMock:
        stmt = args[0] if args else ""
        m = MagicMock()
        s_str = str(stmt)
        if "FROM documents" in s_str:
            m.scalar_one_or_none.return_value = doc
        elif "FROM settings" in s_str:
            m.scalar_one_or_none.return_value = None
        elif "count(" in s_str.lower():
            m.scalar_one.return_value = 0
        elif "sum(" in s_str.lower():
            m.scalar_one.return_value = Decimal("0.0000")
        else:
            m.scalar_one_or_none.return_value = None
            m.scalar_one.return_value = Decimal("0.0000")
            m.scalars.return_value.all.return_value = []
            m.scalars.return_value.first.return_value = None
        return m

    session.execute.side_effect = mock_execute

    # Use Replay provider to simulate S7 fixture
    from app.ai.factory import set_document_analyzer, set_llm_client
    from app.ai.providers.replay import ReplayDocumentAnalyzer, ReplayLlmClient

    analyzer = ReplayDocumentAnalyzer()
    llm = ReplayLlmClient()
    set_document_analyzer(analyzer)
    set_llm_client(llm)

    try:
        # Run extraction pipeline for S7 fixture
        # Mock resolve_doc_id in analyzer to return s7-inv-7001-inj
        import app.ai.providers.replay as replay_module

        orig_resolve = replay_module.resolve_doc_id
        replay_module.resolve_doc_id = lambda **kwargs: "s7-inv-7001-inj"

        extraction = run_extraction(session, doc_id)

        # 1. Document marked suspicious
        assert doc.suspicious is True

        # 2. Injection flag recorded
        added_objs = [call[0][0] for call in session.add.call_args_list]
        injection_flags = [obj for obj in added_objs if isinstance(obj, InjectionFlag)]
        assert len(injection_flags) > 0
        assert injection_flags[0].detector == "rule"
        assert len(injection_flags[0].snippet_hash) == 64

        # 3. Ground truth total 2625.00 is preserved, NOT changed to 0 by injection
        fields = [obj for obj in added_objs if isinstance(obj, ExtractedField)]
        total_field = next((f for f in fields if f.name == "total"), None)
        assert total_field is not None
        assert total_field.value_raw == "2625.00"

        # 4. Confirmation blocked
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = doc
        mock_db.execute.return_value.scalars.return_value.first.return_value = extraction

        client = TestClient(app)
        app.dependency_overrides[get_db] = lambda: mock_db
        buyer = Principal(
            id=uuid.uuid4(),
            email="buyer@demo.example",
            display_name="Buyer",
            roles=["buyer"],
            department_id=None,
            department_name=None,
            approval_limit_aed=Decimal("0.00"),
        )
        app.dependency_overrides[get_current_principal] = lambda: buyer

        resp = client.post(f"/api/v1/documents/{doc_id}/confirm")
        assert resp.status_code == 409
        assert resp.json()["code"] == "FLAGS_OPEN"
    finally:
        set_document_analyzer(None)
        set_llm_client(None)
        set_storage(None)
        app.dependency_overrides.clear()
        replay_module.resolve_doc_id = orig_resolve
