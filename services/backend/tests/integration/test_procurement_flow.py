import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap
from app.core.models import (
    AuditLog,
    Department,
    Document,
    ExtractedField,
    ExtractedLine,
    Extraction,
    POLine,
    PurchaseOrder,
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
def test_full_procurement_flow_pr_to_po_to_odoo(db_session: Session) -> None:
    _clean_db(db_session)
    test_password = "FlowPassword" + uuid.uuid4().hex[:8] + "!"
    bootstrap(db_session, password=test_password)

    client = TestClient(app)

    req_token = _login(client, "requester.fac@demo-holdings.example", test_password)
    buyer_token = _login(client, "buyer1@demo-holdings.example", test_password)
    mgr_token = _login(client, "manager.facilities@demo-holdings.example", test_password)

    fac_dept = db_session.query(Department).filter(Department.name == "Facilities").one()

    # 1. Requester creates PR in draft (AED 20,000 -> Tier 2)
    create_pr_resp = client.post(
        "/api/v1/purchase-requests",
        headers={"Authorization": f"Bearer {req_token}"},
        json={
            "title": "Ergonomic Chairs and Desks",
            "department_id": str(fac_dept.id),
            "lines": [
                {
                    "description": "Ergonomic Office Chair",
                    "qty": 20,
                    "uom": "unit",
                    "est_unit_price": 500.00,
                },
                {
                    "description": "Standing Desk",
                    "qty": 10,
                    "uom": "unit",
                    "est_unit_price": 1000.00,
                },
            ],
        },
    )
    assert create_pr_resp.status_code == 200, create_pr_resp.text
    pr_data = create_pr_resp.json()
    pr_id = pr_data["id"]
    assert Decimal(str(pr_data["total_aed"])) == Decimal("20000.00")
    assert pr_data["status"] == "draft"

    # 2. Requester submits PR -> S1: routes to department Manager
    submit_pr_resp = client.post(
        f"/api/v1/purchase-requests/{pr_id}/submit",
        headers={"Authorization": f"Bearer {req_token}"},
    )
    assert submit_pr_resp.status_code == 200, submit_pr_resp.text
    submitted_pr = submit_pr_resp.json()
    assert submitted_pr["status"] == "submitted"
    assert submitted_pr["rule_snapshot"]["tier"] == 2
    assert submitted_pr["current_approver"] == "Mariam Demo-Manager"

    # 3. Requester inbox is empty (SOD check); Manager inbox has the item
    req_inbox = client.get(
        "/api/v1/approvals/inbox", headers={"Authorization": f"Bearer {req_token}"}
    )
    # Requester role cannot access approvals inbox (403)
    assert req_inbox.status_code == 403

    mgr_inbox = client.get(
        "/api/v1/approvals/inbox", headers={"Authorization": f"Bearer {mgr_token}"}
    )
    assert mgr_inbox.status_code == 200
    mgr_items = mgr_inbox.json()
    assert len(mgr_items) == 1
    step_id = mgr_items[0]["step_id"]
    assert mgr_items[0]["subject_id"] == pr_id

    # 4. Manager approves PR
    approve_resp = client.post(
        f"/api/v1/approvals/{step_id}/decision",
        headers={"Authorization": f"Bearer {mgr_token}"},
        json={"decision": "approve", "comment": "Approved for vendor quotes"},
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["subject_status"] == "approved"

    # 5. Create 2 confirmed quotation documents and extractions
    buyer_user = db_session.query(User).filter(User.email == "buyer1@demo-holdings.example").one()
    vendor1 = Vendor(
        name="Gulf Office Supplies LLC",
        trn="100123456789003",
        payment_terms_days=30,
        created_by=buyer_user.id,
    )
    vendor2 = Vendor(
        name="Emirates Furniture Trading",
        trn="100987654321003",
        payment_terms_days=60,
        created_by=buyer_user.id,
    )
    db_session.add_all([vendor1, vendor2])
    db_session.flush()

    doc1 = Document(
        owner_id=buyer_user.id,
        department_id=fac_dept.id,
        pr_id=uuid.UUID(pr_id),
        vendor_id=vendor1.id,
        doc_type="quote",
        status="confirmed",
        file_sha256=uuid.uuid4().hex,
        blob_path="test/quote1.pdf",
        mime="application/pdf",
        size_bytes=1024,
    )
    doc2 = Document(
        owner_id=buyer_user.id,
        department_id=fac_dept.id,
        pr_id=uuid.UUID(pr_id),
        vendor_id=vendor2.id,
        doc_type="quote",
        status="confirmed",
        file_sha256=uuid.uuid4().hex,
        blob_path="test/quote2.pdf",
        mime="application/pdf",
        size_bytes=1024,
    )
    db_session.add_all([doc1, doc2])
    db_session.flush()

    ext1 = Extraction(document_id=doc1.id, status="completed")
    ext2 = Extraction(document_id=doc2.id, status="completed")
    db_session.add_all([ext1, ext2])
    db_session.flush()

    # Fields and lines for Quote 1 (Gulf Office: 19,000 AED total, 3 days lead time, 60 days terms)
    db_session.add_all(
        [
            ExtractedField(extraction_id=ext1.id, name="total", value_raw="19000.00"),
            ExtractedField(extraction_id=ext1.id, name="lead_time_days", value_raw="3"),
            ExtractedField(extraction_id=ext1.id, name="payment_terms_days", value_raw="60"),
            ExtractedField(extraction_id=ext1.id, name="currency", value_raw="AED"),
            ExtractedField(extraction_id=ext1.id, name="trn", value_raw="100123456789003"),
            ExtractedLine(
                extraction_id=ext1.id,
                line_no=1,
                item_code="CHR-01",
                description="Ergonomic Office Chair",
                qty=Decimal("20.00"),
                unit_price=Decimal("450.00"),
                line_total=Decimal("9000.00"),
            ),
            ExtractedLine(
                extraction_id=ext1.id,
                line_no=2,
                item_code="DSK-01",
                description="Standing Desk",
                qty=Decimal("10.00"),
                unit_price=Decimal("1000.00"),
                line_total=Decimal("10000.00"),
            ),
        ]
    )

    # Fields and lines for Quote 2 (Emirates: 20,500 AED total, 5 days lead time)
    db_session.add_all(
        [
            ExtractedField(extraction_id=ext2.id, name="total", value_raw="20500.00"),
            ExtractedField(extraction_id=ext2.id, name="lead_time_days", value_raw="5"),
            ExtractedField(extraction_id=ext2.id, name="payment_terms_days", value_raw="60"),
            ExtractedField(extraction_id=ext2.id, name="currency", value_raw="AED"),
            ExtractedField(extraction_id=ext2.id, name="trn", value_raw="100987654321003"),
            ExtractedLine(
                extraction_id=ext2.id,
                line_no=1,
                item_code="CHR-02",
                description="Ergonomic Office Chair",
                qty=Decimal("20.00"),
                unit_price=Decimal("500.00"),
                line_total=Decimal("10000.00"),
            ),
            ExtractedLine(
                extraction_id=ext2.id,
                line_no=2,
                item_code="DSK-02",
                description="Standing Desk",
                qty=Decimal("10.00"),
                unit_price=Decimal("1050.00"),
                line_total=Decimal("10500.00"),
            ),
        ]
    )
    db_session.commit()

    # 6. Buyer creates Comparison
    comp_resp = client.post(
        "/api/v1/comparisons",
        headers={"Authorization": f"Bearer {buyer_token}"},
        json={"pr_id": pr_id, "quote_document_ids": [str(doc1.id), str(doc2.id)]},
    )
    assert comp_resp.status_code == 200, comp_resp.text
    comp_data = comp_resp.json()
    comp_id = comp_data["id"]
    assert len(comp_data["quotes"]) == 2
    assert len(comp_data["pairings"]) == 4  # 2 PR lines * 2 quotes

    # 7. Generate recommendation
    rec_resp = client.post(
        f"/api/v1/comparisons/{comp_id}/recommendation",
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert rec_resp.status_code == 200, rec_resp.text
    rec_data = rec_resp.json()
    assert rec_data["recommended_vendor_id"] == str(vendor1.id)
    assert "Recommended vendor: Gulf Office Supplies LLC" in rec_data["explanation"]

    # 8. Buyer decides on recommended vendor
    dec_resp = client.post(
        f"/api/v1/comparisons/{comp_id}/decision",
        headers={"Authorization": f"Bearer {buyer_token}"},
        json={"vendor_id": str(vendor1.id)},
    )
    assert dec_resp.status_code == 200
    assert dec_resp.json()["status"] == "decided"

    # 9. Buyer creates Purchase Order from decided comparison
    po_resp = client.post(
        "/api/v1/purchase-orders",
        headers={"Authorization": f"Bearer {buyer_token}"},
        json={"comparison_id": comp_id},
    )
    assert po_resp.status_code == 200, po_resp.text
    po_data = po_resp.json()
    po_id = po_data["id"]
    assert po_data["status"] == "draft"
    assert Decimal(str(po_data["subtotal"])) == Decimal("19000.00")
    assert Decimal(str(po_data["vat"])) == Decimal("950.00")
    assert Decimal(str(po_data["total"])) == Decimal("19950.00")

    # 10. Buyer submits PO -> routes to Department Manager (Tier 2)
    po_sub_resp = client.post(
        f"/api/v1/purchase-orders/{po_id}/submit",
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert po_sub_resp.status_code == 200, po_sub_resp.text
    po_sub_data = po_sub_resp.json()
    assert po_sub_data["status"] == "submitted"
    assert po_sub_data["current_approver"] == "Mariam Demo-Manager"

    # 11. Manager approves PO
    po_inbox = client.get(
        "/api/v1/approvals/inbox", headers={"Authorization": f"Bearer {mgr_token}"}
    )
    assert po_inbox.status_code == 200
    po_step_id = [item["step_id"] for item in po_inbox.json() if item["subject_id"] == po_id][0]

    po_approve_resp = client.post(
        f"/api/v1/approvals/{po_step_id}/decision",
        headers={"Authorization": f"Bearer {mgr_token}"},
        json={"decision": "approve", "comment": "PO approved"},
    )
    assert po_approve_resp.status_code == 200
    assert po_approve_resp.json()["subject_status"] == "approved"

    # 12. Buyer pushes approved PO to Odoo
    idem_key = "odoo-key-" + uuid.uuid4().hex
    push_resp = client.post(
        f"/api/v1/purchase-orders/{po_id}/push-to-odoo",
        headers={"Authorization": f"Bearer {buyer_token}", "Idempotency-Key": idem_key},
    )
    assert push_resp.status_code == 200, push_resp.text
    push_data = push_resp.json()
    assert push_data["status"] == "sent_to_vendor"
    assert "ODOO-PO" in push_data["odoo_ref"]

    # 13. Idempotent retry with same key
    retry_resp = client.post(
        f"/api/v1/purchase-orders/{po_id}/push-to-odoo",
        headers={"Authorization": f"Bearer {buyer_token}", "Idempotency-Key": idem_key},
    )
    assert retry_resp.status_code == 200
    assert retry_resp.json()["odoo_ref"] == push_data["odoo_ref"]

    _clean_db(db_session)


@pytest.mark.integration
def test_three_way_match_s1_and_s3_scenarios(db_session: Session) -> None:
    _clean_db(db_session)
    test_password = "MatchPassword" + uuid.uuid4().hex[:8] + "!"
    bootstrap(db_session, password=test_password)

    client = TestClient(app)
    buyer_token = _login(client, "buyer1@demo-holdings.example", test_password)
    mgr_token = _login(client, "manager.facilities@demo-holdings.example", test_password)

    buyer_user = db_session.query(User).filter(User.email == "buyer1@demo-holdings.example").one()
    fac_dept = db_session.query(Department).filter(Department.name == "Facilities").one()

    vendor = Vendor(
        name="Fast Distribution LLC",
        trn="100999888777003",
        created_by=buyer_user.id,
    )
    db_session.add(vendor)
    db_session.flush()

    # Create approved PO: 10 units @ 500 AED = 5,000 subtotal, 250 VAT, 5250 total
    po = PurchaseOrder(
        number="PO-2026-MATCH01",
        vendor_id=vendor.id,
        created_by=buyer_user.id,
        department_id=fac_dept.id,
        status="sent_to_vendor",
        subtotal=Decimal("5000.00"),
        vat=Decimal("250.00"),
        total=Decimal("5250.00"),
    )
    db_session.add(po)
    db_session.flush()

    po_line = POLine(
        po_id=po.id,
        line_no=1,
        description="Heavy Duty Storage Shelves",
        qty=Decimal("10.00"),
        uom="unit",
        unit_price=Decimal("500.00"),
        vat_rate=Decimal("0.05"),
        created_by=buyer_user.id,
    )
    db_session.add(po_line)
    db_session.flush()

    # Confirmed Delivery Note: 10 units received
    dn_doc = Document(
        owner_id=buyer_user.id,
        department_id=fac_dept.id,
        po_id=po.id,
        vendor_id=vendor.id,
        doc_type="delivery_note",
        status="confirmed",
        file_sha256=uuid.uuid4().hex,
        blob_path="test/dn.pdf",
        mime="application/pdf",
        size_bytes=1024,
    )
    db_session.add(dn_doc)
    db_session.flush()

    dn_ext = Extraction(document_id=dn_doc.id, status="completed")
    db_session.add(dn_ext)
    db_session.flush()

    db_session.add(
        ExtractedLine(
            extraction_id=dn_ext.id,
            line_no=1,
            description="Heavy Duty Storage Shelves",
            qty=Decimal("10.00"),
        )
    )
    db_session.commit()

    # --- Scenario S1: Perfect Match (Invoice 10 units @ 500 AED) ---
    inv_s1_doc = Document(
        owner_id=buyer_user.id,
        department_id=fac_dept.id,
        po_id=po.id,
        vendor_id=vendor.id,
        doc_type="invoice",
        status="confirmed",
        file_sha256=uuid.uuid4().hex,
        blob_path="test/inv_s1.pdf",
        mime="application/pdf",
        size_bytes=1024,
    )
    db_session.add(inv_s1_doc)
    db_session.flush()

    inv_s1_ext = Extraction(document_id=inv_s1_doc.id, status="completed")
    db_session.add(inv_s1_ext)
    db_session.flush()

    db_session.add_all(
        [
            ExtractedField(extraction_id=inv_s1_ext.id, name="po_number", value_raw=po.number),
            ExtractedField(extraction_id=inv_s1_ext.id, name="vat_amount", value_raw="250.00"),
            ExtractedField(extraction_id=inv_s1_ext.id, name="total", value_raw="5250.00"),
            ExtractedLine(
                extraction_id=inv_s1_ext.id,
                line_no=1,
                description="Heavy Duty Storage Shelves",
                qty=Decimal("10.00"),
                unit_price=Decimal("500.00"),
                line_total=Decimal("5000.00"),
            ),
        ]
    )
    db_session.commit()

    match_s1_resp = client.post(
        "/api/v1/matches",
        headers={"Authorization": f"Bearer {buyer_token}"},
        json={"invoice_document_id": str(inv_s1_doc.id)},
    )
    assert match_s1_resp.status_code == 200, match_s1_resp.text
    s1_data = match_s1_resp.json()
    assert s1_data["overall_status"] == "matched"
    assert len(s1_data["exceptions"]) == 0

    # --- Scenario S3: Quantity Exception (PO 10, DN 10, Invoice 12) ---
    inv_s3_doc = Document(
        owner_id=buyer_user.id,
        department_id=fac_dept.id,
        po_id=po.id,
        vendor_id=vendor.id,
        doc_type="invoice",
        status="confirmed",
        file_sha256=uuid.uuid4().hex,
        blob_path="test/inv_s3.pdf",
        mime="application/pdf",
        size_bytes=1024,
    )
    db_session.add(inv_s3_doc)
    db_session.flush()

    inv_s3_ext = Extraction(document_id=inv_s3_doc.id, status="completed")
    db_session.add(inv_s3_ext)
    db_session.flush()

    db_session.add_all(
        [
            ExtractedField(extraction_id=inv_s3_ext.id, name="po_number", value_raw=po.number),
            ExtractedField(extraction_id=inv_s3_ext.id, name="vat_amount", value_raw="300.00"),
            ExtractedField(extraction_id=inv_s3_ext.id, name="total", value_raw="6300.00"),
            ExtractedLine(
                extraction_id=inv_s3_ext.id,
                line_no=1,
                description="Heavy Duty Storage Shelves",
                qty=Decimal("12.00"),  # 12 invoiced vs 10 received!
                unit_price=Decimal("500.00"),
                line_total=Decimal("6000.00"),
            ),
        ]
    )
    db_session.commit()

    match_s3_resp = client.post(
        "/api/v1/matches",
        headers={"Authorization": f"Bearer {buyer_token}"},
        json={"invoice_document_id": str(inv_s3_doc.id)},
    )
    assert match_s3_resp.status_code == 200, match_s3_resp.text
    s3_data = match_s3_resp.json()
    assert s3_data["overall_status"] == "exception"
    assert len(s3_data["exceptions"]) >= 1

    exc = [e for e in s3_data["exceptions"] if e["kind"] == "qty_variance"][0]
    assert "invoiced 12" in exc["reason"]
    assert "received 10" in exc["reason"]
    assert Decimal(str(exc["amount_impact_aed"])) == Decimal("1000.00")
    exc_id = exc["id"]

    # Buyer attempts to accept over-billed quantity -> 403 BUYER_OVERBILLING_BLOCKED
    buyer_accept_resp = client.post(
        f"/api/v1/exceptions/{exc_id}/resolve",
        headers={"Authorization": f"Bearer {buyer_token}"},
        json={"action": "accept", "reason": "Buyer trying to accept overbilling"},
    )
    assert buyer_accept_resp.status_code == 403
    assert buyer_accept_resp.json()["code"] == "BUYER_OVERBILLING_BLOCKED"

    # Buyer escalates to Manager
    escalate_resp = client.post(
        f"/api/v1/exceptions/{exc_id}/resolve",
        headers={"Authorization": f"Bearer {buyer_token}"},
        json={"action": "escalate", "reason": "Over-billing requires Manager review"},
    )
    assert escalate_resp.status_code == 200
    assert escalate_resp.json()["status"] == "escalated"

    # Manager accepts the exception
    mgr_accept_resp = client.post(
        f"/api/v1/exceptions/{exc_id}/resolve",
        headers={"Authorization": f"Bearer {mgr_token}"},
        json={"action": "accept", "reason": "Manager approved extra units"},
    )
    assert mgr_accept_resp.status_code == 200
    assert mgr_accept_resp.json()["status"] == "accepted"

    _clean_db(db_session)


@pytest.mark.integration
def test_settings_api_and_audit(db_session: Session) -> None:
    _clean_db(db_session)
    test_password = "SettingsPassword" + uuid.uuid4().hex[:8] + "!"
    bootstrap(db_session, password=test_password)

    client = TestClient(app)
    admin_token = _login(client, "admin@demo-holdings.example", test_password)
    buyer_token = _login(client, "buyer1@demo-holdings.example", test_password)

    # 1. Read settings
    get_resp = client.get(
        "/api/v1/settings/thresholds",
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["key"] == "thresholds"
    assert get_resp.json()["version"] >= 1

    # 2. Buyer cannot PUT settings -> 403
    put_buyer_resp = client.put(
        "/api/v1/settings/thresholds",
        headers={"Authorization": f"Bearer {buyer_token}"},
        json={"value": {"test": 123}},
    )
    assert put_buyer_resp.status_code == 403

    # 3. Admin can PUT settings
    put_admin_resp = client.put(
        "/api/v1/settings/thresholds",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"value": [{"tier": 1, "max_amount_aed": "6000.00"}]},
    )
    assert put_admin_resp.status_code == 200
    updated_data = put_admin_resp.json()
    assert updated_data["version"] >= 2

    # 4. Audit trail check for setting update
    audit_entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "setting.updated")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.after["key"] == "approval_tiers"

    _clean_db(db_session)
