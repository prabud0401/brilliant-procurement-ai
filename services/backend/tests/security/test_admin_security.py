import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.models import User, UserRole
from app.core.policy import Principal, get_current_principal
from app.main import app


def _make_principal(
    roles: list[str],
    user_id: uuid.UUID | None = None,
    limit: Decimal = Decimal("0.00"),
) -> Principal:
    return Principal(
        id=user_id or uuid.uuid4(),
        email=f"user-{uuid.uuid4().hex[:6]}@demo.example",
        display_name="Test User",
        roles=roles,
        department_id=uuid.uuid4(),
        department_name="Test Dept",
        approval_limit_aed=limit,
    )


@pytest.mark.security
def test_admin_access_allowed_for_admin_only() -> None:
    client = TestClient(app)

    # 1. Admin allowed (200)
    admin_principal = _make_principal(roles=["admin"])
    mock_db = MagicMock()
    mock_db.query.return_value.order_by.return_value.all.return_value = []
    app.dependency_overrides[get_current_principal] = lambda: admin_principal
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        resp = client.get("/api/v1/admin/integrations")
        assert resp.status_code == 200
        data = resp.json()
        assert any("Odoo (mock adapter)" in item["label"] for item in data)

        resp = client.get("/api/v1/admin/users")
        assert resp.status_code == 200

        resp = client.get("/api/v1/admin/departments")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()


@pytest.mark.security
@pytest.mark.parametrize("role", ["requester", "buyer", "manager"])
def test_admin_access_forbidden_for_non_admin_roles(role: str) -> None:
    client = TestClient(app)
    principal = _make_principal(roles=[role])
    app.dependency_overrides[get_current_principal] = lambda: principal

    try:
        for path in [
            "/api/v1/admin/users",
            "/api/v1/admin/departments",
            "/api/v1/admin/integrations",
            "/api/v1/admin/retention",
        ]:
            resp = client.get(path)
            assert resp.status_code == 403
            assert resp.headers.get("content-type") == "application/problem+json"
            assert resp.json()["code"] == "FORBIDDEN"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.security
def test_reference_data_accessible_to_all_roles() -> None:
    client = TestClient(app)
    mock_db = MagicMock()
    mock_db.query.return_value.order_by.return_value.all.return_value = []
    app.dependency_overrides[get_db] = lambda: mock_db

    for role in ["requester", "buyer", "manager", "admin"]:
        principal = _make_principal(roles=[role])
        app.dependency_overrides[get_current_principal] = lambda: principal

        resp = client.get("/api/v1/vendors")
        assert resp.status_code == 200

        resp = client.get("/api/v1/products")
        assert resp.status_code == 200

    app.dependency_overrides.clear()


@pytest.mark.security
def test_admin_cannot_approve_purchases_403() -> None:
    """Admin role has no business approval permission (API 403 FORBIDDEN)."""
    client = TestClient(app)
    admin_principal = _make_principal(roles=["admin"])
    app.dependency_overrides[get_current_principal] = lambda: admin_principal

    try:
        resp = client.post(
            f"/api/v1/approvals/{uuid.uuid4()}/decision",
            json={"decision": "approve"},
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "FORBIDDEN"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.security
def test_admin_self_granting_business_role_requires_reason() -> None:
    client = TestClient(app)
    admin_id = uuid.uuid4()
    admin_principal = _make_principal(roles=["admin"], user_id=admin_id)

    mock_user = User(
        id=admin_id,
        email="admin@demo.example",
        display_name="Admin User",
        approval_limit_aed=Decimal("0.00"),
        active=True,
        is_demo=False,
    )
    mock_role = UserRole(user_id=admin_id, role="admin")
    mock_user.roles = [mock_role]

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user

    app.dependency_overrides[get_current_principal] = lambda: admin_principal
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        # Attempt without reason -> 400 REASON_REQUIRED
        resp = client.patch(
            f"/api/v1/admin/users/{admin_id}",
            json={"roles": ["admin", "buyer"]},
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == "REASON_REQUIRED"

        # Attempt with short reason -> 400 REASON_REQUIRED
        resp = client.patch(
            f"/api/v1/admin/users/{admin_id}",
            json={"roles": ["admin", "buyer"], "reason": "short"},
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == "REASON_REQUIRED"

        # Attempt with valid reason >= 10 chars -> 200 OK
        resp = client.patch(
            f"/api/v1/admin/users/{admin_id}",
            json={
                "roles": ["admin", "buyer"],
                "reason": "Temporary delegation for quarterly audit testing",
            },
        )
        assert resp.status_code == 200
        assert "buyer" in resp.json()["roles"]
    finally:
        app.dependency_overrides.clear()
