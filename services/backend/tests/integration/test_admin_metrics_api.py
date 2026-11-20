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
