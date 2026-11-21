"""Integration tests for document list titles: vendor_name and document_number (F31)."""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap
from app.core.models import Document, ExtractedField, Extraction, User, Vendor
from app.main import app


def _clean_db(db: Session) -> None:
    db.execute(text("DELETE FROM match_exceptions"))
    db.execute(text("DELETE FROM match_lines"))
    db.execute(text("DELETE FROM matches"))
    db.execute(text("DELETE FROM outbox"))
    db.execute(text("DELETE FROM approval_steps"))
    db.execute(text("DELETE FROM comparison_pairings"))
    db.execute(text("DELETE FROM comparison_quotes"))
    db.execute(text("DELETE FROM comparisons"))
    db.execute(text("DELETE FROM po_lines"))
    db.execute(text("DELETE FROM purchase_orders"))
    db.execute(text("DELETE FROM pr_lines"))
    db.execute(text("DELETE FROM purchase_requests"))
    db.execute(text("DELETE FROM extracted_lines"))
    db.execute(text("DELETE FROM extracted_fields"))
    db.execute(text("DELETE FROM extractions"))
    db.execute(text("DELETE FROM documents"))
    db.execute(text("DELETE FROM vendors"))
    db.execute(text("DELETE FROM user_roles"))
    db.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_no_update_delete"))
    db.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_no_truncate"))
    db.execute(text("TRUNCATE audit_log RESTART IDENTITY CASCADE"))
    db.execute(text("DELETE FROM users"))
    db.execute(text("DELETE FROM departments"))
    db.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_no_update_delete"))
    db.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_no_truncate"))
    db.commit()


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token_str: str = resp.json()["access_token"]
    return token_str


@pytest.mark.integration
def test_list_documents_includes_vendor_and_document_number(db_session: Session) -> None:
    """Document list payload includes vendor_name and document_number; missing values are null."""
    _clean_db(db_session)
    password = "DocPass" + uuid.uuid4().hex[:8] + "!"
    bootstrap(db_session, password=password)

    client = TestClient(app)
    buyer_token = _login(client, "buyer1@demo-holdings.example", password)
    headers = {"Authorization": f"Bearer {buyer_token}"}
    buyer_user = db_session.query(User).filter(User.email == "buyer1@demo-holdings.example").first()
    assert buyer_user is not None
    buyer_id = buyer_user.id

    # 1. Create a linked Vendor
    vendor = Vendor(
        id=uuid.uuid4(),
        name="Gulf Line IT Trading",
        trn="100000000000003",
        payment_terms_days=30,
    )
    db_session.add(vendor)
    db_session.flush()

    # 2. Doc 1: Linked vendor + extraction with document_number
    doc1 = Document(
        id=uuid.uuid4(),
        owner_id=buyer_id,
        vendor_id=vendor.id,
        doc_type="quote",
        status="confirmed",
        file_sha256="sha256_dummy_doc1_" + uuid.uuid4().hex[:16],
        blob_path="doc1.pdf",
        mime="application/pdf",
        pages=1,
        size_bytes=1024,
        source="upload",
    )
    db_session.add(doc1)
    db_session.flush()

    ext1 = Extraction(
        id=uuid.uuid4(),
        document_id=doc1.id,
        version=1,
        status="completed",
    )
    db_session.add(ext1)
    db_session.flush()

    field1 = ExtractedField(
        id=uuid.uuid4(),
        extraction_id=ext1.id,
        name="document_number",
        value_raw="Q-1042",
        status="ok",
        confidence=Decimal("0.95"),
    )
    db_session.add(field1)

    # 3. Doc 2: Unlinked vendor, but extraction has vendor_name and quote_number fallback
    doc2 = Document(
        id=uuid.uuid4(),
        owner_id=buyer_id,
        vendor_id=None,
        doc_type="quote",
        status="confirmed",
        file_sha256="sha256_dummy_doc2_" + uuid.uuid4().hex[:16],
        blob_path="doc2.pdf",
        mime="application/pdf",
        pages=1,
        size_bytes=2048,
        source="upload",
    )
    db_session.add(doc2)
    db_session.flush()

    ext2 = Extraction(
        id=uuid.uuid4(),
        document_id=doc2.id,
        version=1,
        status="completed",
    )
    db_session.add(ext2)
    db_session.flush()

    field2a = ExtractedField(
        id=uuid.uuid4(),
        extraction_id=ext2.id,
        name="vendor_name",
        value_raw="Falcon Supplies LLC",
        status="ok",
        confidence=Decimal("0.90"),
    )
    field2b = ExtractedField(
        id=uuid.uuid4(),
        extraction_id=ext2.id,
        name="quote_number",
        value_raw="Q-8821",
        status="ok",
        confidence=Decimal("0.92"),
    )
    db_session.add_all([field2a, field2b])

    # 4. Doc 3: No vendor, no extraction (empty/null values)
    doc3 = Document(
        id=uuid.uuid4(),
        owner_id=buyer_id,
        vendor_id=None,
        doc_type="other",
        status="queued",
        file_sha256="sha256_dummy_doc3_" + uuid.uuid4().hex[:16],
        blob_path="doc3.pdf",
        mime="application/pdf",
        pages=1,
        size_bytes=512,
        source="upload",
    )
    db_session.add(doc3)
    db_session.commit()

    # Query GET /api/v1/documents
    resp = client.get("/api/v1/documents", headers=headers)
    assert resp.status_code == 200, f"Failed to list documents: {resp.text}"

    items = resp.json()
    item_map = {item["id"]: item for item in items}

    # Verify doc 1
    assert str(doc1.id) in item_map
    d1_data = item_map[str(doc1.id)]
    assert d1_data["vendor_name"] == "Gulf Line IT Trading"
    assert d1_data["document_number"] == "Q-1042"

    # Verify doc 2
    assert str(doc2.id) in item_map
    d2_data = item_map[str(doc2.id)]
    assert d2_data["vendor_name"] == "Falcon Supplies LLC"
    assert d2_data["document_number"] == "Q-8821"

    # Verify doc 3 (missing values are null, not errors)
    assert str(doc3.id) in item_map
    d3_data = item_map[str(doc3.id)]
    assert d3_data["vendor_name"] is None
    assert d3_data["document_number"] is None
