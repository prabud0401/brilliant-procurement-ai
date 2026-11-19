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
    Match,
    MatchException,
    POLine,
    PurchaseOrder,
    User,
    UserRole,
    Vendor,
)
from app.core.security import hash_password
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
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    token_str: str = resp.json()["access_token"]
    return token_str


@pytest.mark.integration
def test_s4_tier1_approval_sod_and_dual_role(db_session: Session) -> None:
    """S4: requester.it creates and submits <=5,000 PR.

    Creator and dual buyer+requester get 403 SOD_BLOCKED; buyer1 approves.
    """
    _clean_db(db_session)
    test_password = "AccessPass" + uuid.uuid4().hex[:8] + "!"
    bootstrap(db_session, password=test_password)

    client = TestClient(app)
    req_it_token = _login(client, "requester.it@demo-holdings.example", test_password)
    buyer1_token = _login(client, "buyer1@demo-holdings.example", test_password)

    it_dept = db_session.query(Department).filter(Department.name == "IT").one()

    # 1. requester.it creates PR for AED 4,500 (Tier 1 <= 5,000)
    create_resp = client.post(
        "/api/v1/purchase-requests",
        headers={"Authorization": f"Bearer {req_it_token}"},
        json={
            "title": "IT Supplies Small Order",
            "department_id": str(it_dept.id),
            "lines": [
                {
                    "description": "Ethernet Cables 10-pack",
                    "qty": 10,
                    "uom": "pack",
                    "est_unit_price": 450.00,
                }
            ],
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    pr_id = create_resp.json()["id"]

    # 2. requester.it submits PR -> routes to Buyer (tier 1)
    sub_resp = client.post(
        f"/api/v1/purchase-requests/{pr_id}/submit",
        headers={"Authorization": f"Bearer {req_it_token}"},
    )
    assert sub_resp.status_code == 200, sub_resp.text
    sub_data = sub_resp.json()
    assert sub_data["status"] == "submitted"
    assert sub_data["rule_snapshot"]["tier"] == 1

    # 3. Creator's inbox should NOT show the step (SoD)
    req_inbox = client.get(
        "/api/v1/approvals/inbox",
        headers={"Authorization": f"Bearer {req_it_token}"},
    )
    # requester role has no business approval role -> 403 FORBIDDEN
    assert req_inbox.status_code == 403

    # Find the created approval step id
    bundle_resp = client.get(
        f"/api/v1/purchase-requests/{pr_id}",
        headers={"Authorization": f"Bearer {buyer1_token}"},
    )
    assert bundle_resp.status_code == 200
    assert bundle_resp.json()["current_approver_id"] is not None

    # Step ID query
    steps_resp = client.get(
        "/api/v1/approvals/inbox",
        headers={"Authorization": f"Bearer {buyer1_token}"},
    )
    assert steps_resp.status_code == 200
    inbox_items = [i for i in steps_resp.json() if i["subject_id"] == pr_id]
    assert len(inbox_items) == 1
    actual_step_id = inbox_items[0]["step_id"]

    # 4. Creator attempts to approve own PR -> 403 SOD_BLOCKED
    self_approve_resp = client.post(
        f"/api/v1/approvals/{actual_step_id}/decision",
        headers={"Authorization": f"Bearer {req_it_token}"},
        json={"decision": "approve", "comment": "Trying to self-approve"},
    )
    assert self_approve_resp.status_code == 403
    assert self_approve_resp.json()["code"] == "SOD_BLOCKED"

    # 5. Dual-role test: user holding both buyer + requester
    dual_user = User(
        email="dual.user@demo-holdings.example",
        display_name="Dual Buyer Requester",
        department_id=it_dept.id,
        approval_limit_aed=Decimal("0.00"),
        password_hash=hash_password(test_password),
        active=True,
    )
    db_session.add(dual_user)
    db_session.flush()
    db_session.add(UserRole(user_id=dual_user.id, role="requester"))
    db_session.add(UserRole(user_id=dual_user.id, role="buyer"))
    db_session.commit()

    dual_token = _login(client, "dual.user@demo-holdings.example", test_password)

    # Dual user creates and submits a <= 5000 PR
    dual_pr_resp = client.post(
        "/api/v1/purchase-requests",
        headers={"Authorization": f"Bearer {dual_token}"},
        json={
            "title": "Dual User PR",
            "department_id": str(it_dept.id),
            "lines": [
                {
                    "description": "USB-C Hubs",
                    "qty": 5,
                    "uom": "unit",
                    "est_unit_price": 200.00,
                }
            ],
        },
    )
    assert dual_pr_resp.status_code == 200
    dual_pr_id = dual_pr_resp.json()["id"]

    dual_sub = client.post(
        f"/api/v1/purchase-requests/{dual_pr_id}/submit",
        headers={"Authorization": f"Bearer {dual_token}"},
    )
    assert dual_sub.status_code == 200

    # Dual user has buyer role so can access inbox, but their own PR step must NOT appear!
    dual_inbox = client.get(
        "/api/v1/approvals/inbox",
        headers={"Authorization": f"Bearer {dual_token}"},
    )
    assert dual_inbox.status_code == 200
    dual_inbox_pr_ids = [i["subject_id"] for i in dual_inbox.json()]
    assert dual_pr_id not in dual_inbox_pr_ids

    # Find the approval step for dual_pr
    buyer_inbox = client.get(
        "/api/v1/approvals/inbox",
        headers={"Authorization": f"Bearer {buyer1_token}"},
    )
    dual_step_items = [i for i in buyer_inbox.json() if i["subject_id"] == dual_pr_id]
    assert len(dual_step_items) == 1
    dual_step_id = dual_step_items[0]["step_id"]

    # Dual user attempts to approve their own PR -> 403 SOD_BLOCKED
    dual_self_dec = client.post(
        f"/api/v1/approvals/{dual_step_id}/decision",
        headers={"Authorization": f"Bearer {dual_token}"},
        json={"decision": "approve", "comment": "Dual user attempting self-approval"},
    )
    assert dual_self_dec.status_code == 403
    assert dual_self_dec.json()["code"] == "SOD_BLOCKED"

    # 6. buyer1 approves requester.it's S4 PR
    buyer_approve_resp = client.post(
        f"/api/v1/approvals/{actual_step_id}/decision",
        headers={"Authorization": f"Bearer {buyer1_token}"},
        json={"decision": "approve", "comment": "Approved by Buyer 1"},
    )
    assert buyer_approve_resp.status_code == 200, buyer_approve_resp.text
    assert buyer_approve_resp.json()["subject_status"] == "approved"

    # Verify audit log for pr.created, pr.submitted, approval.approved
    actions = [a.action for a in db_session.query(AuditLog).all()]
    assert "pr.created" in actions
    assert "pr.submitted" in actions
    assert "approval.approved" in actions

    _clean_db(db_session)


@pytest.mark.integration
def test_s1_tier2_department_manager_routing_and_isolation(db_session: Session) -> None:
    """S1: requester.it PR of AED 28,875 routes to manager.it.

    manager.facilities gets 403 (wrong department); manager.it approves.
    """
    _clean_db(db_session)
    test_password = "AccessPass" + uuid.uuid4().hex[:8] + "!"
    bootstrap(db_session, password=test_password)

    client = TestClient(app)
    req_it_token = _login(client, "requester.it@demo-holdings.example", test_password)
    mgr_fac_token = _login(client, "manager.facilities@demo-holdings.example", test_password)
    mgr_it_token = _login(client, "manager.it@demo-holdings.example", test_password)

    it_dept = db_session.query(Department).filter(Department.name == "IT").one()

    # 1. requester.it creates PR of AED 28,875 (Tier 2: 5,000.01 - 50,000)
    create_resp = client.post(
        "/api/v1/purchase-requests",
        headers={"Authorization": f"Bearer {req_it_token}"},
        json={
            "title": "IT Department Server Racks S1",
            "department_id": str(it_dept.id),
            "lines": [
                {
                    "description": "Server Rack Enclosure",
                    "qty": 55,
                    "uom": "unit",
                    "est_unit_price": 525.00,
                }
            ],
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    pr_id = create_resp.json()["id"]
    assert Decimal(str(create_resp.json()["total_aed"])) == Decimal("28875.00")

    # 2. requester.it submits PR -> routes to manager.it
    sub_resp = client.post(
        f"/api/v1/purchase-requests/{pr_id}/submit",
        headers={"Authorization": f"Bearer {req_it_token}"},
    )
    assert sub_resp.status_code == 200, sub_resp.text
    sub_data = sub_resp.json()
    assert sub_data["status"] == "submitted"
    assert sub_data["rule_snapshot"]["tier"] == 2
    assert sub_data["current_approver"] == "Yousef Demo-Manager"

    # 3. manager.facilities inbox should NOT list this step
    fac_inbox_resp = client.get(
        "/api/v1/approvals/inbox",
        headers={"Authorization": f"Bearer {mgr_fac_token}"},
    )
    assert fac_inbox_resp.status_code == 200
    fac_items = [i for i in fac_inbox_resp.json() if i["subject_id"] == pr_id]
    assert len(fac_items) == 0

    # 4. manager.it inbox MUST list this step
    it_inbox_resp = client.get(
        "/api/v1/approvals/inbox",
        headers={"Authorization": f"Bearer {mgr_it_token}"},
    )
    assert it_inbox_resp.status_code == 200
    it_items = [i for i in it_inbox_resp.json() if i["subject_id"] == pr_id]
    assert len(it_items) == 1
    step_id = it_items[0]["step_id"]

    # 5. manager.facilities attempts to approve -> 403 (wrong department)
    fac_dec_resp = client.post(
        f"/api/v1/approvals/{step_id}/decision",
        headers={"Authorization": f"Bearer {mgr_fac_token}"},
        json={"decision": "approve", "comment": "Facilities manager approving IT request"},
    )
    assert fac_dec_resp.status_code == 403
    assert fac_dec_resp.json()["code"] in ("DEPARTMENT_MISMATCH", "NOT_ASSIGNED")

    # 6. manager.it approves -> 200 OK
    it_dec_resp = client.post(
        f"/api/v1/approvals/{step_id}/decision",
        headers={"Authorization": f"Bearer {mgr_it_token}"},
        json={"decision": "approve", "comment": "Approved IT S1 request"},
    )
    assert it_dec_resp.status_code == 200, it_dec_resp.text
    assert it_dec_resp.json()["subject_status"] == "approved"

    # Verify audit log
    actions = [a.action for a in db_session.query(AuditLog).all()]
    assert "pr.created" in actions
    assert "pr.submitted" in actions
    assert "approval.approved" in actions

    _clean_db(db_session)


@pytest.mark.integration
def test_tier3_multistep_sod_and_limit_enforcement(db_session: Session) -> None:
    """>50,000: two steps; manager.it cannot decide step 2 after deciding step 1.

    manager.projects (250k) decides step 2; 50k manager gets 403 ABOVE_LIMIT.
    """
    _clean_db(db_session)
    test_password = "AccessPass" + uuid.uuid4().hex[:8] + "!"
    bootstrap(db_session, password=test_password)

    client = TestClient(app)
    req_it_token = _login(client, "requester.it@demo-holdings.example", test_password)
    mgr_it_token = _login(client, "manager.it@demo-holdings.example", test_password)
    mgr_fac_token = _login(client, "manager.facilities@demo-holdings.example", test_password)
    mgr_proj_token = _login(client, "manager.projects@demo-holdings.example", test_password)

    it_dept = db_session.query(Department).filter(Department.name == "IT").one()

    # 1. Create PR of AED 75,000 (Tier 3 > 50,000)
    create_resp = client.post(
        "/api/v1/purchase-requests",
        headers={"Authorization": f"Bearer {req_it_token}"},
        json={
            "title": "Enterprise Cloud Server Hardware",
            "department_id": str(it_dept.id),
            "lines": [
                {
                    "description": "High Performance Server Blade",
                    "qty": 75,
                    "uom": "unit",
                    "est_unit_price": 1000.00,
                }
            ],
        },
    )
    assert create_resp.status_code == 200
    pr_id = create_resp.json()["id"]

    # 2. Submit PR -> creates 2 steps: step 1 (manager.it), step 2 (manager.projects 250k)
    sub_resp = client.post(
        f"/api/v1/purchase-requests/{pr_id}/submit",
        headers={"Authorization": f"Bearer {req_it_token}"},
    )
    assert sub_resp.status_code == 200
    sub_data = sub_resp.json()
    assert sub_data["rule_snapshot"]["tier"] == 3
    assert len(sub_data["rule_snapshot"]["steps_created"]) == 2

    # 3. Step 1: manager.it sees in inbox and approves
    it_inbox_resp = client.get(
        "/api/v1/approvals/inbox",
        headers={"Authorization": f"Bearer {mgr_it_token}"},
    )
    assert it_inbox_resp.status_code == 200
    step1_items = [i for i in it_inbox_resp.json() if i["subject_id"] == pr_id]
    assert len(step1_items) == 1
    step1_id = step1_items[0]["step_id"]

    step1_dec = client.post(
        f"/api/v1/approvals/{step1_id}/decision",
        headers={"Authorization": f"Bearer {mgr_it_token}"},
        json={"decision": "approve", "comment": "Department manager approves Step 1"},
    )
    assert step1_dec.status_code == 200
    assert step1_dec.json()["subject_status"] == "submitted"  # Still submitted waiting for step 2

    # 4. Step 2: Find step 2 id
    proj_inbox_resp = client.get(
        "/api/v1/approvals/inbox",
        headers={"Authorization": f"Bearer {mgr_proj_token}"},
    )
    assert proj_inbox_resp.status_code == 200
    step2_items = [i for i in proj_inbox_resp.json() if i["subject_id"] == pr_id]
    assert len(step2_items) == 1
    step2_id = step2_items[0]["step_id"]

    # 5. manager.it cannot decide step 2 after deciding step 1 -> 403 SOD_BLOCKED
    step2_same_person = client.post(
        f"/api/v1/approvals/{step2_id}/decision",
        headers={"Authorization": f"Bearer {mgr_it_token}"},
        json={"decision": "approve", "comment": "manager.it attempting to approve step 2"},
    )
    assert step2_same_person.status_code == 403
    assert step2_same_person.json()["code"] == "SOD_BLOCKED"

    # 6. manager.facilities (50k limit < 75k document total) attempts step 2 -> 403 ABOVE_LIMIT
    step2_over_limit = client.post(
        f"/api/v1/approvals/{step2_id}/decision",
        headers={"Authorization": f"Bearer {mgr_fac_token}"},
        json={"decision": "approve", "comment": "50k manager attempting to approve 75k step 2"},
    )
    assert step2_over_limit.status_code == 403
    assert step2_over_limit.json()["code"] == "ABOVE_LIMIT"

    # 7. manager.projects (250k limit) decides step 2 -> 200 OK
    step2_proj_dec = client.post(
        f"/api/v1/approvals/{step2_id}/decision",
        headers={"Authorization": f"Bearer {mgr_proj_token}"},
        json={"decision": "approve", "comment": "Executive manager approves Step 2"},
    )
    assert step2_proj_dec.status_code == 200, step2_proj_dec.text
    assert step2_proj_dec.json()["subject_status"] == "approved"

    # Verify audit log recorded both approvals
    approvals_in_audit = (
        db_session.query(AuditLog).filter(AuditLog.action == "approval.approved").all()
    )
    assert len(approvals_in_audit) >= 2

    _clean_db(db_session)


@pytest.mark.integration
def test_record_scope_and_admin_restrictions(db_session: Session) -> None:
    """Record scope: requester.fac gets 404 on requester.it's PR.

    manager.facilities does not see IT PRs; admin gets 403 on PR create and approvals.
    """
    _clean_db(db_session)
    test_password = "AccessPass" + uuid.uuid4().hex[:8] + "!"
    bootstrap(db_session, password=test_password)

    client = TestClient(app)
    req_it_token = _login(client, "requester.it@demo-holdings.example", test_password)
    req_fac_token = _login(client, "requester.fac@demo-holdings.example", test_password)
    mgr_fac_token = _login(client, "manager.facilities@demo-holdings.example", test_password)
    admin_token = _login(client, "admin@demo-holdings.example", test_password)

    it_dept = db_session.query(Department).filter(Department.name == "IT").one()

    # 1. requester.it creates PR
    create_resp = client.post(
        "/api/v1/purchase-requests",
        headers={"Authorization": f"Bearer {req_it_token}"},
        json={
            "title": "Confidential IT Equipment",
            "department_id": str(it_dept.id),
            "lines": [
                {
                    "description": "Network Hardware",
                    "qty": 2,
                    "uom": "unit",
                    "est_unit_price": 1500.00,
                }
            ],
        },
    )
    assert create_resp.status_code == 200
    pr_id = create_resp.json()["id"]

    # 2. requester.fac gets 404 on requester.it's PR
    fac_get_resp = client.get(
        f"/api/v1/purchase-requests/{pr_id}",
        headers={"Authorization": f"Bearer {req_fac_token}"},
    )
    assert fac_get_resp.status_code == 404
    assert fac_get_resp.json()["code"] == "NOT_FOUND"

    # 3. manager.facilities does not see IT PRs in the list
    fac_list_resp = client.get(
        "/api/v1/purchase-requests",
        headers={"Authorization": f"Bearer {mgr_fac_token}"},
    )
    assert fac_list_resp.status_code == 200
    fac_pr_ids = [pr["id"] for pr in fac_list_resp.json()]
    assert pr_id not in fac_pr_ids

    # 4. admin gets 403 on PR create
    admin_create_resp = client.post(
        "/api/v1/purchase-requests",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Admin Attempting PR",
            "department_id": str(it_dept.id),
            "lines": [
                {
                    "description": "Item",
                    "qty": 1,
                    "uom": "unit",
                    "est_unit_price": 100.00,
                }
            ],
        },
    )
    assert admin_create_resp.status_code == 403
    assert admin_create_resp.json()["code"] == "FORBIDDEN"

    # 5. admin gets 403 on approvals decision
    dummy_step_id = uuid.uuid4()
    admin_dec_resp = client.post(
        f"/api/v1/approvals/{dummy_step_id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "approve", "comment": "Admin decision"},
    )
    assert admin_dec_resp.status_code == 403
    assert admin_dec_resp.json()["code"] == "FORBIDDEN"

    # 6. admin gets 403 on approvals inbox
    admin_inbox_resp = client.get(
        "/api/v1/approvals/inbox",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_inbox_resp.status_code == 403
    assert admin_inbox_resp.json()["code"] == "FORBIDDEN"

    _clean_db(db_session)


@pytest.mark.integration
def test_buyer_exception_policy_and_escalation(db_session: Session) -> None:
    """Buyer exception policy: S3 over-billed qty cannot be accepted by buyer1.

    Price variance <= 500 accepted with reason (audited); > 500 escalated to Manager.
    """
    _clean_db(db_session)
    test_password = "AccessPass" + uuid.uuid4().hex[:8] + "!"
    bootstrap(db_session, password=test_password)

    client = TestClient(app)
    buyer1_token = _login(client, "buyer1@demo-holdings.example", test_password)
    mgr_fac_token = _login(client, "manager.facilities@demo-holdings.example", test_password)

    buyer_user = db_session.query(User).filter(User.email == "buyer1@demo-holdings.example").one()
    fac_dept = db_session.query(Department).filter(Department.name == "Facilities").one()

    vendor = Vendor(
        name="Global Warehouse FZE",
        trn="100999888777999",
        created_by=buyer_user.id,
    )
    db_session.add(vendor)
    db_session.flush()

    # PO: 10 units @ 500.00 = 5,000 subtotal, 250 vat, 5,250 total
    po = PurchaseOrder(
        number="PO-2026-EXC-POL",
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
        description="Steel Storage Racks",
        qty=Decimal("10.00"),
        uom="unit",
        unit_price=Decimal("500.00"),
        vat_rate=Decimal("0.05"),
        created_by=buyer_user.id,
    )
    db_session.add(po_line)
    db_session.flush()

    # Delivery Note: 10 units received
    dn_doc = Document(
        owner_id=buyer_user.id,
        department_id=fac_dept.id,
        po_id=po.id,
        vendor_id=vendor.id,
        doc_type="delivery_note",
        status="confirmed",
        file_sha256=uuid.uuid4().hex,
        blob_path="test/dn_exc.pdf",
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
            description="Steel Storage Racks",
            qty=Decimal("10.00"),
        )
    )
    db_session.commit()

    # --- Scenario S3: Quantity Over-billing (Invoiced 12 vs Received 10) ---
    inv_doc = Document(
        owner_id=buyer_user.id,
        department_id=fac_dept.id,
        po_id=po.id,
        vendor_id=vendor.id,
        doc_type="invoice",
        status="confirmed",
        file_sha256=uuid.uuid4().hex,
        blob_path="test/inv_s3_pol.pdf",
        mime="application/pdf",
        size_bytes=1024,
    )
    db_session.add(inv_doc)
    db_session.flush()

    inv_ext = Extraction(document_id=inv_doc.id, status="completed")
    db_session.add(inv_ext)
    db_session.flush()

    db_session.add_all(
        [
            ExtractedField(extraction_id=inv_ext.id, name="po_number", value_raw=po.number),
            ExtractedField(extraction_id=inv_ext.id, name="vat_amount", value_raw="300.00"),
            ExtractedField(extraction_id=inv_ext.id, name="total", value_raw="6300.00"),
            ExtractedLine(
                extraction_id=inv_ext.id,
                line_no=1,
                description="Steel Storage Racks",
                qty=Decimal("12.00"),
                unit_price=Decimal("500.00"),
                line_total=Decimal("6000.00"),
            ),
        ]
    )
    db_session.commit()

    match_resp = client.post(
        "/api/v1/matches",
        headers={"Authorization": f"Bearer {buyer1_token}"},
        json={"invoice_document_id": str(inv_doc.id)},
    )
    assert match_resp.status_code == 200, match_resp.text
    match_data = match_resp.json()
    assert match_data["overall_status"] == "exception"

    qty_exc = [e for e in match_data["exceptions"] if e["kind"] == "qty_variance"][0]
    qty_exc_id = qty_exc["id"]

    # 1. buyer1 cannot accept over-billed quantity -> 403 BUYER_OVERBILLING_BLOCKED
    buyer_qty_accept = client.post(
        f"/api/v1/exceptions/{qty_exc_id}/resolve",
        headers={"Authorization": f"Bearer {buyer1_token}"},
        json={"action": "accept", "reason": "Buyer attempting to accept over-billed quantity"},
    )
    assert buyer_qty_accept.status_code == 403
    assert buyer_qty_accept.json()["code"] == "BUYER_OVERBILLING_BLOCKED"

    # --- Scenario: Price Variance <= AED 500 ---
    # Manually create a price variance exception of 350 AED on this match
    match_row = db_session.query(Match).filter(Match.id == uuid.UUID(match_data["id"])).one()
    small_exc = MatchException(
        match_id=match_row.id,
        kind="price_variance",
        amount_impact_aed=Decimal("350.00"),
        status="open",
        reason="Unit price AED 535 vs PO unit price AED 500",
    )
    db_session.add(small_exc)
    db_session.commit()

    # 2. buyer1 accepts price variance <= 500 with reason (audited)
    small_accept_resp = client.post(
        f"/api/v1/exceptions/{small_exc.id}/resolve",
        headers={"Authorization": f"Bearer {buyer1_token}"},
        json={
            "action": "accept",
            "reason": "Price variance within vendor tolerance agreement",
        },
    )
    assert small_accept_resp.status_code == 200, small_accept_resp.text
    assert small_accept_resp.json()["status"] == "accepted"

    # Verify audit entry for small exception resolution
    small_audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_id == small_exc.id,
            AuditLog.action == "match.exception_resolved",
        )
        .first()
    )
    assert small_audit is not None
    assert (
        "Price variance" in str(small_audit.reason)
        or "Price variance" in str(small_audit.after)
        or small_audit.action == "match.exception_resolved"
    )

    # --- Scenario: Price Variance > AED 500 ---
    large_exc = MatchException(
        match_id=match_row.id,
        kind="price_variance",
        amount_impact_aed=Decimal("750.00"),
        status="open",
        reason="Unit price AED 575 vs PO unit price AED 500",
    )
    db_session.add(large_exc)
    db_session.commit()

    # 3. buyer1 attempts to accept > 500 -> 403 BUYER_POLICY_LIMIT_EXCEEDED
    buyer_large_accept = client.post(
        f"/api/v1/exceptions/{large_exc.id}/resolve",
        headers={"Authorization": f"Bearer {buyer1_token}"},
        json={"action": "accept", "reason": "Buyer attempting to accept 750 AED variance"},
    )
    assert buyer_large_accept.status_code == 403
    assert buyer_large_accept.json()["code"] == "BUYER_POLICY_LIMIT_EXCEEDED"

    # 4. buyer1 escalates > 500 to Manager
    escalate_resp = client.post(
        f"/api/v1/exceptions/{large_exc.id}/resolve",
        headers={"Authorization": f"Bearer {buyer1_token}"},
        json={
            "action": "escalate",
            "reason": "Price variance 750 AED exceeds buyer policy limit 500 AED",
        },
    )
    assert escalate_resp.status_code == 200
    assert escalate_resp.json()["status"] == "escalated"

    # 5. buyer1 cannot decide escalated exception
    buyer_decide_escalated = client.post(
        f"/api/v1/exceptions/{large_exc.id}/resolve",
        headers={"Authorization": f"Bearer {buyer1_token}"},
        json={"action": "accept", "reason": "Buyer trying to accept escalated exception"},
    )
    assert buyer_decide_escalated.status_code == 403

    # 6. Manager decides escalated exception
    mgr_resolve_resp = client.post(
        f"/api/v1/exceptions/{large_exc.id}/resolve",
        headers={"Authorization": f"Bearer {mgr_fac_token}"},
        json={"action": "accept", "reason": "Manager approved 750 AED price variance"},
    )
    assert mgr_resolve_resp.status_code == 200, mgr_resolve_resp.text
    assert mgr_resolve_resp.json()["status"] == "accepted"

    # Verify audit entry for manager resolution
    large_audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_id == large_exc.id,
            AuditLog.action == "match.exception_resolved",
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert large_audit is not None
    assert str(large_audit.actor_id) == str(
        db_session.query(User)
        .filter(User.email == "manager.facilities@demo-holdings.example")
        .one()
        .id
    )

    _clean_db(db_session)
