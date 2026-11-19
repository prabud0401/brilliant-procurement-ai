import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.models import AuditLog
from app.core.policy import Principal, get_current_principal, scope_filter
from app.main import app


@pytest.mark.security
def test_audit_write_endpoints_return_405() -> None:
    client = TestClient(app)

    paths = [
        "/api/v1/audit",
        "/api/v1/audit/",
        "/api/v1/audit/123",
        "/api/v1/audit/export.csv",
    ]

    for path in paths:
        for method in ["put", "patch", "delete"]:
            if method == "delete":
                resp = client.delete(path)
            elif method == "put":
                resp = client.put(path, json={"foo": "bar"})
            else:
                resp = client.patch(path, json={"foo": "bar"})

            assert resp.status_code == 405, (
                f"Expected 405 for {method.upper()} on {path}, got {resp.status_code}"
            )
            data = resp.json()
            assert data["code"] == "METHOD_NOT_ALLOWED"
            assert resp.headers["content-type"] == "application/problem+json"


@pytest.mark.security
def test_audit_export_csv_rbac() -> None:
    """Only admin can export audit CSV; other roles get 403."""
    admin_user = Principal(
        id=uuid.uuid4(),
        email="admin@demo.example",
        display_name="Admin",
        roles=["admin"],
        department_id=None,
        department_name=None,
        approval_limit_aed=Decimal("0.00"),
    )
    buyer_user = Principal(
        id=uuid.uuid4(),
        email="buyer@demo.example",
        display_name="Buyer",
        roles=["buyer"],
        department_id=None,
        department_name=None,
        approval_limit_aed=Decimal("0.00"),
    )

    client = TestClient(app)

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    mock_db.query.return_value.order_by.return_value.all.return_value = []

    def override_get_db() -> MagicMock:
        return mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        # When authenticated as Buyer -> 403
        app.dependency_overrides[get_current_principal] = lambda: buyer_user
        resp = client.get("/api/v1/audit/export.csv")
        assert resp.status_code == 403
        assert resp.json()["code"] == "FORBIDDEN"

        # When authenticated as Admin -> 200 (CSV stream)
        app.dependency_overrides[get_current_principal] = lambda: admin_user
        resp = client.get("/api/v1/audit/export.csv")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "audit_export.csv" in resp.headers["content-disposition"]
        assert "id,occurred_at,actor_id" in resp.text
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_principal, None)


@pytest.mark.security
def test_audit_listing_scope_filters() -> None:
    """Verify scope_filter isolates records between requester, manager, and admin."""
    dept_a_id = uuid.uuid4()
    requester_a_id = uuid.uuid4()
    requester_a = Principal(
        id=requester_a_id,
        email="req.a@demo.example",
        display_name="Requester A",
        roles=["requester"],
        department_id=dept_a_id,
        department_name="Facilities",
        approval_limit_aed=Decimal("0.00"),
    )

    manager_a = Principal(
        id=uuid.uuid4(),
        email="mgr.a@demo.example",
        display_name="Manager A",
        roles=["manager"],
        department_id=dept_a_id,
        department_name="Facilities",
        approval_limit_aed=Decimal("50000.00"),
    )

    admin = Principal(
        id=uuid.uuid4(),
        email="admin@demo.example",
        display_name="Admin",
        roles=["admin"],
        department_id=None,
        department_name=None,
        approval_limit_aed=Decimal("0.00"),
    )

    # Requester filter must restrict to actor_id == requester.id
    req_filter = scope_filter(requester_a, "audit.view", AuditLog)
    assert str(req_filter) == str(AuditLog.actor_id == requester_a_id)

    # Manager filter must restrict to department members
    mgr_filter = scope_filter(manager_a, "audit.view", AuditLog)
    assert "users.department_id =" in str(mgr_filter) or "IN (" in str(mgr_filter)

    # Admin filter is unrestricted (true())
    admin_filter = scope_filter(admin, "audit.view", AuditLog)
    assert str(admin_filter).lower() == "true"
