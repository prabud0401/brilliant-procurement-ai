from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap
from app.core.models import Department, User
from app.main import app


@pytest.mark.integration
def test_bootstrap_idempotent_and_roles_login(db_session: Session) -> None:
    test_password = "SecureDemoPassword123!"

    # Clean up to guarantee fresh start for idempotency test
    db_session.execute(text("DELETE FROM user_roles"))
    db_session.execute(text("DELETE FROM users"))
    db_session.execute(text("DELETE FROM departments"))
    db_session.commit()

    # Run 1: First bootstrap
    res1 = bootstrap(db_session, password=test_password)
    assert res1["departments_created"] == 3
    assert res1["users_created"] == 7

    # Verify counts in DB
    assert db_session.query(Department).count() == 3
    assert db_session.query(User).count() == 7

    # Run 2: Second bootstrap (idempotency check)
    res2 = bootstrap(db_session, password=test_password)
    assert res2["departments_created"] == 0
    assert res2["users_created"] == 0
    assert res2["users_updated"] == 7

    # Counts must remain unchanged
    assert db_session.query(Department).count() == 3
    assert db_session.query(User).count() == 7

    client = TestClient(app)

    # Test login and /me for each demo user role
    accounts = [
        ("requester.fac@demo-holdings.example", ["requester"], Decimal("0.00"), "Facilities"),
        ("requester.it@demo-holdings.example", ["requester"], Decimal("0.00"), "IT"),
        ("buyer1@demo-holdings.example", ["buyer"], Decimal("0.00"), "Facilities"),
        ("buyer2@demo-holdings.example", ["buyer"], Decimal("0.00"), "IT"),
        (
            "manager.facilities@demo-holdings.example",
            ["manager"],
            Decimal("50000.00"),
            "Facilities",
        ),
        ("manager.projects@demo-holdings.example", ["manager"], Decimal("250000.00"), "Projects"),
        ("admin@demo-holdings.example", ["admin"], Decimal("0.00"), "IT"),
    ]

    for email, expected_roles, expected_limit, expected_dept in accounts:
        # Standard login
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": test_password},
        )
        assert login_resp.status_code == 200, f"Login failed for {email}: {login_resp.text}"
        data = login_resp.json()
        token = data["access_token"]
        assert token is not None

        # Verify /me
        me_resp = client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200, f"/me failed for {email}: {me_resp.text}"
        me_data = me_resp.json()
        assert me_data["email"] == email
        assert me_data["roles"] == expected_roles
        assert Decimal(str(me_data["approval_limit_aed"])) == expected_limit
        assert me_data["department_name"] == expected_dept
        assert me_data["is_demo"] is True
        assert me_data["active"] is True

        # Demo login check
        demo_resp = client.post(
            "/api/v1/auth/demo-login",
            json={"username": email},
        )
        assert demo_resp.status_code == 200
