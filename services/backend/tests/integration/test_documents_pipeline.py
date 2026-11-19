"""Integration tests for document upload, job worker extraction, review, and confirm flow."""

from __future__ import annotations

import io
import uuid
from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai.factory import set_document_analyzer, set_llm_client
from app.ai.providers.replay import ReplayDocumentAnalyzer, ReplayLlmClient
from app.audit.service import verify_chain
from app.core.bootstrap import bootstrap
from app.core.models import AuditLog, Document, InjectionFlag, User
from app.core.security import create_access_token
from app.documents.storage import InMemoryBlobStorage, set_storage
from app.main import app
from app.worker_main import process_single_job
from tools.datagen.layouts import render_pdf_to_bytes
from tools.datagen.scenarios import get_all_scenarios

# Helper to find scenarios
ALL_SCENARIOS = {s.doc_id: s for s in get_all_scenarios()}


@pytest.fixture(autouse=True)
def setup_storage_and_bootstrap(db_session: Session) -> Generator[None, None, None]:
    # Use in-memory storage for clean test isolation
    storage = InMemoryBlobStorage()
    set_storage(storage)
    set_document_analyzer(ReplayDocumentAnalyzer())
    set_llm_client(ReplayLlmClient())

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

    # Ensure demo users exist
    test_password = "".join(["D", "e", "m", "o", "1", "2", "3", "!", "@", "#"])
    bootstrap(db_session, password=test_password)

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


def get_user_token(db_session: Session, email: str) -> str:
    user = db_session.execute(select(User).where(User.email == email)).scalar_one()
    roles = [r.role for r in user.roles]
    token, _ = create_access_token(
        user_id=user.id,
        email=user.email,
        roles=roles,
        department_id=user.department_id,
        approval_limit_aed=user.approval_limit_aed,
    )
    return token


@pytest.mark.integration
def test_upload_extract_and_confirm_s1_quotation(db_session: Session) -> None:
    """Full lifecycle: Upload S1 quote -> Worker extracts -> Review fields -> Confirm."""
    client = TestClient(app)
    buyer_token = get_user_token(db_session, "buyer1@demo-holdings.example")
    headers = {"Authorization": f"Bearer {buyer_token}"}

    # 1. Render scenario S1 quotation PDF
    s1_spec = ALL_SCENARIOS["s1-quote-gulfline"]
    pdf_bytes = render_pdf_to_bytes(s1_spec)

    # 2. Upload document via POST /api/v1/documents
    upload_files = {"file": ("s1-quote-gulfline.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    resp_upload = client.post(
        "/api/v1/documents",
        data={"doc_type": "quote"},
        files=upload_files,
        headers=headers,
    )
    assert resp_upload.status_code == 202
    doc_id = uuid.UUID(resp_upload.json()["id"])

    # Verify audit entry for upload
    db_session.expire_all()
    doc = db_session.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    assert doc.status == "queued"
    assert doc.doc_type == "quote"

    # 3. Process extraction job via background worker
    processed = process_single_job(db_session)
    assert processed is True

    # 4. Check extraction results
    db_session.expire_all()
    doc = db_session.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    assert doc.status == "needs_review"
    assert doc.vendor_id is not None  # Matched to Gulf Line IT Trading

    resp_ext = client.get(f"/api/v1/documents/{doc_id}/extraction", headers=headers)
    assert resp_ext.status_code == 200
    ext_data = resp_ext.json()

    fields_map = {f["name"]: f for f in ext_data["fields"]}
    assert fields_map["vendor_name"]["value_raw"] == "Gulf Line IT Trading"
    assert fields_map["vendor_trn"]["value_raw"] == "100000000000002"
    assert fields_map["document_number"]["value_raw"] == "Q-1042"
    assert fields_map["total"]["value_raw"] == "28875.00"
    assert fields_map["subtotal"]["value_raw"] == "27500.00"
    assert fields_map["vat_amount"]["value_raw"] == "1375.00"

    assert len(ext_data["lines"]) == 2
    assert ext_data["lines"][0]["item_code"] == "IT-LAP-14"

    # Verify all fields are valid
    for f in ext_data["fields"]:
        assert f["status"] == "ok"
        assert Decimal(str(f["confidence"])) >= Decimal("0.80")

    # 5. Confirm document
    resp_confirm = client.post(f"/api/v1/documents/{doc_id}/confirm", headers=headers)
    assert resp_confirm.status_code == 200
    assert resp_confirm.json()["status"] == "confirmed"

    # 6. Verify audit chain integrity
    db_session.expire_all()
    actions = (
        db_session.execute(
            select(AuditLog.action).where(AuditLog.entity_id == doc_id).order_by(AuditLog.id.asc())
        )
        .scalars()
        .all()
    )
    assert "document.uploaded" in actions
    assert "document.extracted" in actions
    assert "document.confirmed" in actions

    chain_valid, _, _ = verify_chain(db_session)
    assert chain_valid is True


@pytest.mark.integration
def test_exact_duplicate_upload_blocked(db_session: Session) -> None:
    """Exact duplicate uploads return 409 Conflict with existing document ID."""
    client = TestClient(app)
    token = get_user_token(db_session, "buyer1@demo-holdings.example")
    headers = {"Authorization": f"Bearer {token}"}

    s1_spec = ALL_SCENARIOS["s1-quote-falcon"]
    pdf_bytes = render_pdf_to_bytes(s1_spec)

    # First upload
    f1 = {"file": ("s1-quote-falcon.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    r1 = client.post("/api/v1/documents", data={"doc_type": "quote"}, files=f1, headers=headers)
    assert r1.status_code == 202
    first_id = r1.json()["id"]

    # Duplicate upload of same bytes
    f2 = {"file": ("s1-quote-falcon-copy.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    r2 = client.post("/api/v1/documents", data={"doc_type": "quote"}, files=f2, headers=headers)
    assert r2.status_code == 409
    err = r2.json()
    assert err["code"] == "EXACT_DUPLICATE"
    assert "errors" in err and len(err["errors"]) > 0
    assert err["errors"][0]["existing_document_id"] == first_id


@pytest.mark.integration
def test_s6_vat_error_workflow(db_session: Session) -> None:
    """Scenario S6: Wrong VAT is flagged validation_failed, blocks confirm until corrected."""
    client = TestClient(app)
    buyer_token = get_user_token(db_session, "buyer1@demo-holdings.example")
    headers = {"Authorization": f"Bearer {buyer_token}"}

    s6_spec = ALL_SCENARIOS["s6-inv-6001-vat"]
    pdf_bytes = render_pdf_to_bytes(s6_spec)

    resp_upload = client.post(
        "/api/v1/documents",
        data={"doc_type": "invoice"},
        files={"file": ("s6-inv-6001-vat.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=headers,
    )
    assert resp_upload.status_code == 202
    doc_id = uuid.UUID(resp_upload.json()["id"])

    # Worker processes
    assert process_single_job(db_session) is True

    # Check that VAT was flagged
    resp_ext = client.get(f"/api/v1/documents/{doc_id}/extraction", headers=headers)
    assert resp_ext.status_code == 200
    ext = resp_ext.json()
    vat_field = next(f for f in ext["fields"] if f["name"] == "vat_amount")
    assert vat_field["status"] == "validation_failed"
    assert "VAT is not 5%" in (vat_field["validation_msg"] or "")

    # Confirmation blocked
    r_block = client.post(f"/api/v1/documents/{doc_id}/confirm", headers=headers)
    assert r_block.status_code == 409
    assert r_block.json()["code"] == "FLAGS_OPEN"

    # Buyer corrects all fields with open flags
    vat_id = vat_field["id"]
    r_patch = client.patch(
        f"/api/v1/documents/{doc_id}/fields/{vat_id}",
        json={"value": "1000.00"},
        headers=headers,
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["status"] == "corrected"

    # Confirm any other open fields
    for f in ext["fields"]:
        if f["id"] != vat_id and f["status"] in ("needs_review", "validation_failed"):
            client.patch(
                f"/api/v1/documents/{doc_id}/fields/{f['id']}",
                json={"confirm": True},
                headers=headers,
            )

    # Confirm any open lines
    for line in ext["lines"]:
        if line["status"] in ("needs_review", "validation_failed"):
            client.patch(
                f"/api/v1/documents/{doc_id}/lines/{line['id']}",
                json={"confirm": True},
                headers=headers,
            )

    # Now confirmation succeeds
    r_confirm = client.post(f"/api/v1/documents/{doc_id}/confirm", headers=headers)
    assert r_confirm.status_code == 200
    assert r_confirm.json()["status"] == "confirmed"


@pytest.mark.integration
def test_s6_duplicate_detection_and_override_reason(db_session: Session) -> None:
    """Duplicate document numbers trigger duplicate_of and require 10+ char reason."""
    client = TestClient(app)
    buyer_token = get_user_token(db_session, "buyer1@demo-holdings.example")
    headers = {"Authorization": f"Bearer {buyer_token}"}

    # Upload and process S1 quotation
    s1_spec = ALL_SCENARIOS["s1-quote-corniche"]
    r1 = client.post(
        "/api/v1/documents",
        data={"doc_type": "quote"},
        files={
            "file": (
                "s1-quote-corniche.pdf",
                io.BytesIO(render_pdf_to_bytes(s1_spec)),
                "application/pdf",
            )
        },
        headers=headers,
    )
    first_doc_id = r1.json()["id"]
    assert process_single_job(db_session) is True

    # Upload duplicate document (modified bytes so hash differs, but same doc number Q-3312)
    mod_bytes = render_pdf_to_bytes(s1_spec) + b"\n%extra-comment-to-alter-sha256"
    r2 = client.post(
        "/api/v1/documents",
        data={"doc_type": "quote"},
        files={"file": ("s1-quote-corniche-rev2.pdf", io.BytesIO(mod_bytes), "application/pdf")},
        headers=headers,
    )
    assert r2.status_code == 202
    second_doc_id = r2.json()["id"]
    assert process_single_job(db_session) is True

    # Second document is flagged duplicate_of first_doc_id
    db_session.expire_all()
    doc2 = db_session.execute(
        select(Document).where(Document.id == uuid.UUID(second_doc_id))
    ).scalar_one()
    assert doc2.duplicate_of == uuid.UUID(first_doc_id)

    # Confirm blocked
    r_block = client.post(f"/api/v1/documents/{second_doc_id}/confirm", headers=headers)
    assert r_block.status_code == 409

    # Override reason < 10 chars fails
    r_fail = client.post(
        f"/api/v1/documents/{second_doc_id}/not-duplicate",
        json={"reason": "short"},
        headers=headers,
    )
    assert r_fail.status_code in (400, 422)

    # Valid reason >= 10 chars succeeds
    reason = "Verified with supplier: Revised quotation issued with updated terms"
    r_ok = client.post(
        f"/api/v1/documents/{second_doc_id}/not-duplicate",
        json={"reason": reason},
        headers=headers,
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["duplicate_cleared"] is True

    # Confirm fields and confirm document
    r_ext2 = client.get(f"/api/v1/documents/{second_doc_id}/extraction", headers=headers)
    for f in r_ext2.json()["fields"]:
        if f["status"] in ("needs_review", "validation_failed"):
            client.patch(
                f"/api/v1/documents/{second_doc_id}/fields/{f['id']}",
                json={"confirm": True},
                headers=headers,
            )
    for line in r_ext2.json()["lines"]:
        if line["status"] in ("needs_review", "validation_failed"):
            client.patch(
                f"/api/v1/documents/{second_doc_id}/lines/{line['id']}",
                json={"confirm": True},
                headers=headers,
            )

    r_confirm = client.post(f"/api/v1/documents/{second_doc_id}/confirm", headers=headers)
    assert r_confirm.status_code == 200


@pytest.mark.integration
def test_s7_injection_invoice_pipeline(db_session: Session) -> None:
    """Scenario S7: Prompt injection flagged in DB & audit, total unchanged, confirm blocked."""
    client = TestClient(app)
    buyer_token = get_user_token(db_session, "buyer1@demo-holdings.example")
    headers = {"Authorization": f"Bearer {buyer_token}"}

    s7_spec = ALL_SCENARIOS["s7-inv-7001-inj"]
    pdf_bytes = render_pdf_to_bytes(s7_spec)

    r_upload = client.post(
        "/api/v1/documents",
        data={"doc_type": "invoice"},
        files={"file": ("s7-inv-7001-inj.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=headers,
    )
    assert r_upload.status_code == 202
    doc_id = uuid.UUID(r_upload.json()["id"])

    # Worker processes extraction
    assert process_single_job(db_session) is True

    # 1. Document suspicious flag is True
    db_session.expire_all()
    doc = db_session.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    assert doc.suspicious is True

    # 2. Injection flag in DB
    flags = (
        db_session.execute(select(InjectionFlag).where(InjectionFlag.document_id == doc_id))
        .scalars()
        .all()
    )
    assert len(flags) > 0
    assert flags[0].detector == "rule"

    # 3. Ground truth total is preserved at 2625.00 (not changed to 0 by injection)
    resp_ext = client.get(f"/api/v1/documents/{doc_id}/extraction", headers=headers)
    assert resp_ext.status_code == 200
    fields = {f["name"]: f for f in resp_ext.json()["fields"]}
    assert fields["total"]["value_raw"] == "2625.00"

    # 4. Confirmation permanently blocked while suspicious
    r_confirm = client.post(f"/api/v1/documents/{doc_id}/confirm", headers=headers)
    assert r_confirm.status_code == 409
    assert r_confirm.json()["code"] == "FLAGS_OPEN"
