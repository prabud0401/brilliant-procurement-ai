from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.models import User
from app.core.security import create_access_token
from app.main import app


@pytest.mark.integration
def test_admin_and_reference_integration(db_session: Session) -> None:
    """Integration test verifying app/admin and app/reference endpoints against real Postgres."""
    client = TestClient(app)

    # Fetch admin and buyer user from DB
    admin_user = db_session.query(User).filter(User.email == "admin@demo-holdings.example").first()
    buyer_user = db_session.query(User).filter(User.email == "buyer1@demo-holdings.example").first()
    assert admin_user is not None
    assert buyer_user is not None

    admin_token, _ = create_access_token(admin_user.id, email=admin_user.email, roles=["admin"])
    buyer_token, _ = create_access_token(buyer_user.id, email=buyer_user.email, roles=["buyer"])

    # 1. Reference endpoints - accessible to buyer and admin
    r_vendors = client.get("/api/v1/vendors", headers={"Authorization": f"Bearer {buyer_token}"})
    assert r_vendors.status_code == 200
    vendors_data = r_vendors.json()
    assert len(vendors_data) >= 1
    assert "name" in vendors_data[0]

    r_products = client.get("/api/v1/products", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_products.status_code == 200
    products_data = r_products.json()
    assert len(products_data) >= 1
    assert "name" in products_data[0]

    # 2. Admin users endpoint - Admin gets 200, Buyer gets 403
    r_admin_users_forbidden = client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {buyer_token}"}
    )
    assert r_admin_users_forbidden.status_code == 403

    r_admin_users = client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r_admin_users.status_code == 200
    users = r_admin_users.json()
    assert len(users) >= 8

    # 3. Admin integrations endpoint
    r_integ = client.get(
        "/api/v1/admin/integrations", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r_integ.status_code == 200
    integ_data = r_integ.json()
    assert len(integ_data) == 4
    odoo_item = next(i for i in integ_data if i["adapter"] == "odoo")
    assert "Odoo (mock adapter)" in odoo_item["label"]

    # 4. Admin departments
    r_depts = client.get(
        "/api/v1/admin/departments", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r_depts.status_code == 200
    assert len(r_depts.json()) >= 3

    # 5. Admin updates a user's approval limit
    r_patch = client.patch(
        f"/api/v1/admin/users/{buyer_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"approval_limit_aed": "12500.00"},
    )
    assert r_patch.status_code == 200
    updated = r_patch.json()
    assert Decimal(str(updated["approval_limit_aed"])) == Decimal("12500.00")

    # 6. Admin settings history
    r_hist = client.get(
        "/api/v1/admin/settings/approval_policy/history",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_hist.status_code == 200
    assert isinstance(r_hist.json(), list)
