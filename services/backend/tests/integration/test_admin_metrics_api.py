"""Integration tests for GET /api/v1/admin/metrics endpoint access control and values."""

from __future__ import annotations

from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap
from app.core.models import User
from app.core.security import create_access_token
from app.main import app


@pytest.fixture(autouse=True)
def setup_seed(db_session: Session, migrator_url: str) -> Generator[None, None, None]:
    from seed.load import run_seed

    run_seed(db_url=migrator_url)
    bootstrap(db_session, password="TestPassword123!")
    yield


@pytest.mark.integration
def test_admin_metrics_endpoint_access_control(db_session: Session) -> None:
    client = TestClient(app)

    users = db_session.execute(select(User)).scalars().all()
    user_map = {u.email: u for u in users}

    admin = user_map["admin@demo-holdings.example"]
    buyer = user_map["buyer1@demo-holdings.example"]
    requester = user_map["requester.fac@demo-holdings.example"]
    manager = user_map["manager.facilities@demo-holdings.example"]

    admin_token, _ = create_access_token(
        user_id=admin.id, email=admin.email, roles=["admin"], department_id=admin.department_id
    )
    buyer_token, _ = create_access_token(
        user_id=buyer.id, email=buyer.email, roles=["buyer"], department_id=buyer.department_id
    )
    req_token, _ = create_access_token(
        user_id=requester.id,
        email=requester.email,
        roles=["requester"],
        department_id=requester.department_id,
    )
    mgr_token, _ = create_access_token(
        user_id=manager.id,
        email=manager.email,
        roles=["manager"],
        department_id=manager.department_id,
    )

    # 1. Non-admin roles must receive 403 Forbidden
    res_buyer = client.get(
        "/api/v1/admin/metrics", headers={"Authorization": f"Bearer {buyer_token}"}
    )
    assert res_buyer.status_code == 403

    res_req = client.get("/api/v1/admin/metrics", headers={"Authorization": f"Bearer {req_token}"})
    assert res_req.status_code == 403

    res_mgr = client.get("/api/v1/admin/metrics", headers={"Authorization": f"Bearer {mgr_token}"})
    assert res_mgr.status_code == 403

    # 2. Admin receives 200 OK with valid metrics
    res_admin = client.get(
        "/api/v1/admin/metrics", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin.status_code == 200
    data = res_admin.json()

    assert "documents_processed" in data
    assert "share_of_fields_needing_review" in data
    assert "correction_rate_per_field" in data
    assert "match_exception_rate" in data
    assert "approval_cycle_time_seconds" in data
    assert "ai_today" in data
    assert "qa_refusal_rate" in data

    assert data["ai_today"]["daily_budget_aed"] > 0
    assert isinstance(data["correction_rate_per_field"], list)

    assert "spend_by_department" in data
    assert isinstance(data["spend_by_department"], list)
    assert len(data["spend_by_department"]) == 6
    dept_names = [d["department_name"] for d in data["spend_by_department"]]
    assert set(dept_names) == {"Facilities", "IT", "Projects", "Finance", "HR", "Operations"}
    for item in data["spend_by_department"]:
        assert "department_id" in item
        assert "purchase_requests_count" in item
        assert "purchase_requests_total_aed" in item
        assert "purchase_orders_count" in item
        assert "purchase_orders_total_aed" in item
        assert "pending_approvals_count" in item


@pytest.mark.integration
def test_admin_metrics_spend_by_department_aggregation(db_session: Session) -> None:
    from decimal import Decimal

    from app.core.models import ApprovalStep, Department, PurchaseOrder, PurchaseRequest, Vendor

    client = TestClient(app)

    users = db_session.execute(select(User)).scalars().all()
    user_map = {u.email: u for u in users}
    admin = user_map["admin@demo-holdings.example"]
    admin_token, _ = create_access_token(
        user_id=admin.id, email=admin.email, roles=["admin"], department_id=admin.department_id
    )

    depts = db_session.execute(select(Department)).scalars().all()
    dept_map = {d.name: d for d in depts}
    vendor = db_session.execute(select(Vendor)).scalars().first()
    assert vendor is not None

    fin_dept = dept_map["Finance"]
    it_dept = dept_map["IT"]

    req_fin = user_map["requester.finance@demo-holdings.example"]
    buyer_it = user_map["buyer2@demo-holdings.example"]

    # 1. Create a PR in Finance
    pr = PurchaseRequest(
        number="PR-TEST-FIN-001",
        requester_id=req_fin.id,
        department_id=fin_dept.id,
        title="Finance Auditing Tools",
        status="submitted",
        total_aed=Decimal("1500.00"),
        currency="AED",
    )
    db_session.add(pr)
    db_session.flush()

    # 2. Add pending approval step for the Finance PR
    step = ApprovalStep(
        subject_type="pr",
        subject_id=pr.id,
        sequence=1,
        tier=1,
        status="pending",
        created_by=req_fin.id,
    )
    db_session.add(step)

    # 3. Create a PO in IT
    po = PurchaseOrder(
        number="PO-TEST-IT-001",
        vendor_id=vendor.id,
        created_by=buyer_it.id,
        department_id=it_dept.id,
        status="submitted",
        subtotal=Decimal("3000.00"),
        vat=Decimal("150.00"),
        total=Decimal("3150.00"),
        currency="AED",
    )
    db_session.add(po)
    db_session.commit()

    # Query metrics endpoint as Admin
    res = client.get("/api/v1/admin/metrics", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    metrics_data = res.json()

    spend_data = {d["department_name"]: d for d in metrics_data["spend_by_department"]}
    assert len(spend_data) == 6

    # Verify Finance aggregation
    assert spend_data["Finance"]["purchase_requests_count"] >= 1
    assert spend_data["Finance"]["purchase_requests_total_aed"] >= 1500.0
    assert spend_data["Finance"]["pending_approvals_count"] >= 1

    # Verify IT aggregation
    assert spend_data["IT"]["purchase_orders_count"] >= 1
    assert spend_data["IT"]["purchase_orders_total_aed"] >= 3150.0

    # Verify HR has 0 rows
    assert spend_data["HR"]["purchase_requests_count"] == 0
    assert spend_data["HR"]["purchase_requests_total_aed"] == 0.0
    assert spend_data["HR"]["purchase_orders_count"] == 0
    assert spend_data["HR"]["purchase_orders_total_aed"] == 0.0
    assert spend_data["HR"]["pending_approvals_count"] == 0

    # Clean up test rows so other integration tests have clean state
    db_session.delete(step)
    db_session.delete(pr)
    db_session.delete(po)
    db_session.commit()
