"""Integration tests for F34 Demo UI improvements."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap
from app.core.models import (
    ApprovalStep,
    Department,
    Document,
    PurchaseOrder,
    PurchaseRequest,
    User,
    Vendor,
)
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
def test_po_payload_vendor_name_and_approval_history(db_session: Session) -> None:
    """PO payload includes vendor_name and approval_steps with approver names and decided_at."""
    _clean_db(db_session)
    password = "PoPass" + uuid.uuid4().hex[:8] + "!"
    bootstrap(db_session, password=password)

    client = TestClient(app)
    buyer_token = _login(client, "buyer1@demo-holdings.example", password)
    headers = {"Authorization": f"Bearer {buyer_token}"}

    buyer_user = db_session.query(User).filter(User.email == "buyer1@demo-holdings.example").first()
    mariam = (
        db_session.query(User)
        .filter(User.email == "manager.facilities@demo-holdings.example")
        .first()
    )
    khalid = (
        db_session.query(User)
        .filter(User.email == "manager.projects@demo-holdings.example")
        .first()
    )
    assert buyer_user and mariam and khalid

    # Create Vendor
    vendor = Vendor(
        id=uuid.uuid4(),
        name="Gulf Line IT Trading",
        trn="100000000000003",
        payment_terms_days=30,
    )
    db_session.add(vendor)
    db_session.flush()

    # Create PO
    dept = db_session.query(Department).filter(Department.name == "Facilities").first()
    assert dept

    po = PurchaseOrder(
        id=uuid.uuid4(),
        number="PO-2026-6D79D3",
        vendor_id=vendor.id,
        created_by=buyer_user.id,
        department_id=dept.id,
        status="approved",
        subtotal=Decimal("27500.00"),
        vat=Decimal("1375.00"),
        total=Decimal("28875.00"),
        currency="AED",
    )
    db_session.add(po)
    db_session.flush()

    # Create 2 Approval Steps
    now1 = datetime(2026, 11, 20, 10, 30, tzinfo=timezone.utc)
    now2 = datetime(2026, 11, 20, 14, 15, tzinfo=timezone.utc)

    step1 = ApprovalStep(
        id=uuid.uuid4(),
        subject_type="po",
        subject_id=po.id,
        sequence=1,
        tier=2,
        assigned_to=mariam.id,
        status="approved",
        decided_by=mariam.id,
        decided_at=now1,
        comment="Approved within Facilities budget",
    )
    step2 = ApprovalStep(
        id=uuid.uuid4(),
        subject_type="po",
        subject_id=po.id,
        sequence=2,
        tier=3,
        assigned_to=khalid.id,
        status="approved",
        decided_by=khalid.id,
        decided_at=now2,
        comment="Tier 3 secondary approval granted",
    )
    db_session.add_all([step1, step2])
    db_session.commit()

    # 1. Test GET /api/v1/purchase-orders/{id}
    resp = client.get(f"/api/v1/purchase-orders/{po.id}", headers=headers)
    assert resp.status_code == 200, resp.text
    po_data = resp.json()
    assert po_data["vendor_name"] == "Gulf Line IT Trading"
    assert "approval_steps" in po_data
    steps = po_data["approval_steps"]
    assert len(steps) == 2
    assert steps[0]["sequence"] == 1
    assert steps[0]["approver_name"] == mariam.display_name
    assert steps[0]["decided_at"] is not None
    assert steps[0]["comment"] == "Approved within Facilities budget"

    assert steps[1]["sequence"] == 2
    assert steps[1]["approver_name"] == khalid.display_name
    assert steps[1]["decided_at"] is not None
    assert steps[1]["comment"] == "Tier 3 secondary approval granted"

    # 2. Test GET /api/v1/purchase-orders/{id}/approval-history
    resp_hist = client.get(f"/api/v1/purchase-orders/{po.id}/approval-history", headers=headers)
    assert resp_hist.status_code == 200, resp_hist.text
    hist_data = resp_hist.json()
    assert len(hist_data) == 2
    assert hist_data[0]["approver_name"] == mariam.display_name
    assert hist_data[1]["approver_name"] == khalid.display_name


@pytest.mark.integration
def test_pr_payload_and_approval_history(db_session: Session) -> None:
    """PR payload and approval-history endpoint return approver names and decided_at."""
    _clean_db(db_session)
    password = "PrPass" + uuid.uuid4().hex[:8] + "!"
    bootstrap(db_session, password=password)

    client = TestClient(app)
    buyer_token = _login(client, "buyer1@demo-holdings.example", password)
    headers = {"Authorization": f"Bearer {buyer_token}"}

    buyer_user = db_session.query(User).filter(User.email == "buyer1@demo-holdings.example").first()
    mariam = (
        db_session.query(User)
        .filter(User.email == "manager.facilities@demo-holdings.example")
        .first()
    )
    dept = db_session.query(Department).filter(Department.name == "Facilities").first()
    assert buyer_user and mariam and dept

    pr = PurchaseRequest(
        id=uuid.uuid4(),
        number="PR-2026-427C5B",
        requester_id=buyer_user.id,
        department_id=dept.id,
        title="Facilities Fit-out",
        status="approved",
        total_aed=Decimal("62800.00"),
        currency="AED",
    )
    db_session.add(pr)
    db_session.flush()

    now = datetime(2026, 11, 20, 11, 0, tzinfo=timezone.utc)
    step = ApprovalStep(
        id=uuid.uuid4(),
        subject_type="pr",
        subject_id=pr.id,
        sequence=1,
        tier=2,
        assigned_to=mariam.id,
        status="approved",
        decided_by=mariam.id,
        decided_at=now,
        comment="PR approved",
    )
    db_session.add(step)
    db_session.commit()

    resp = client.get(f"/api/v1/purchase-requests/{pr.id}", headers=headers)
    assert resp.status_code == 200, resp.text
    pr_data = resp.json()
    assert len(pr_data["approval_steps"]) == 1
    assert pr_data["approval_steps"][0]["approver_name"] == mariam.display_name
    assert pr_data["approval_steps"][0]["decided_at"] is not None

    resp_hist = client.get(f"/api/v1/purchase-requests/{pr.id}/approval-history", headers=headers)
    assert resp_hist.status_code == 200, resp_hist.text
    hist_steps = resp_hist.json()
    assert len(hist_steps) == 1
    assert hist_steps[0]["approver_name"] == mariam.display_name


@pytest.mark.integration
def test_audit_list_includes_human_entity_labels(db_session: Session) -> None:
    """Audit list items include a human entity_label for a document and a user."""
    _clean_db(db_session)
    password = "AuditPass" + uuid.uuid4().hex[:8] + "!"
    bootstrap(db_session, password=password)

    client = TestClient(app)
    admin_token = _login(client, "admin@demo-holdings.example", password)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Query GET /api/v1/audit
    resp = client.get("/api/v1/audit?limit=50", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    items = data["items"]
    assert len(items) > 0

    # User entity row from bootstrap has human entity_label
    user_items = [it for it in items if it["entity_type"] == "user"]
    if user_items:
        assert any(
            it["entity_label"] is not None and "Demo" in it["entity_label"] for it in user_items
        )


@pytest.mark.integration
def test_list_documents_filter_suspicious_and_confirmed(db_session: Session) -> None:
    """Document list filter returns only confirmed, non-suspicious invoices."""
    _clean_db(db_session)
    password = "DocFPass" + uuid.uuid4().hex[:8] + "!"
    bootstrap(db_session, password=password)

    client = TestClient(app)
    buyer_token = _login(client, "buyer1@demo-holdings.example", password)
    headers = {"Authorization": f"Bearer {buyer_token}"}
    buyer_user = db_session.query(User).filter(User.email == "buyer1@demo-holdings.example").first()
    assert buyer_user

    # 1. Confirmed non-suspicious invoice
    doc_confirmed = Document(
        id=uuid.uuid4(),
        owner_id=buyer_user.id,
        doc_type="invoice",
        status="confirmed",
        file_sha256="sha256_confirmed_" + uuid.uuid4().hex[:16],
        blob_path="doc_conf.pdf",
        mime="application/pdf",
        pages=1,
        size_bytes=1024,
        source="upload",
        suspicious=False,
    )

    # 2. Suspicious invoice (like INV-7001)
    doc_suspicious = Document(
        id=uuid.uuid4(),
        owner_id=buyer_user.id,
        doc_type="invoice",
        status="needs_review",
        file_sha256="sha256_suspicious_" + uuid.uuid4().hex[:16],
        blob_path="doc_susp.pdf",
        mime="application/pdf",
        pages=1,
        size_bytes=1024,
        source="upload",
        suspicious=True,
    )

    # 3. Unconfirmed invoice (needs_review)
    doc_unconfirmed = Document(
        id=uuid.uuid4(),
        owner_id=buyer_user.id,
        doc_type="invoice",
        status="needs_review",
        file_sha256="sha256_unconf_" + uuid.uuid4().hex[:16],
        blob_path="doc_unconf.pdf",
        mime="application/pdf",
        pages=1,
        size_bytes=1024,
        source="upload",
        suspicious=False,
    )

    db_session.add_all([doc_confirmed, doc_suspicious, doc_unconfirmed])
    db_session.commit()

    resp = client.get(
        "/api/v1/documents?doc_type=invoice&status=confirmed&suspicious=false", headers=headers
    )
    assert resp.status_code == 200, resp.text
    docs = resp.json()
    doc_ids = [d["id"] for d in docs]

    assert str(doc_confirmed.id) in doc_ids
    assert str(doc_suspicious.id) not in doc_ids
    assert str(doc_unconfirmed.id) not in doc_ids
