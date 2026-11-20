import uuid
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
    db_session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_no_update_delete"))
    db_session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_no_truncate"))
    db_session.execute(text("TRUNCATE audit_log RESTART IDENTITY CASCADE"))
    db_session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_no_update_delete"))
    db_session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_no_truncate"))
    db_session.execute(text("DELETE FROM match_exceptions"))
    db_session.execute(text("DELETE FROM match_lines"))
    db_session.execute(text("DELETE FROM matches"))
    db_session.execute(text("DELETE FROM outbox"))
    db_session.execute(text("DELETE FROM approval_steps"))
    db_session.execute(text("DELETE FROM po_lines"))
    db_session.execute(text("DELETE FROM purchase_orders"))
    db_session.execute(text("DELETE FROM pr_lines"))
    db_session.execute(text("DELETE FROM purchase_requests"))
    db_session.execute(text("DELETE FROM user_roles"))
    db_session.execute(text("DELETE FROM users"))
    db_session.execute(text("DELETE FROM departments"))
    db_session.commit()

    # Run 1: First bootstrap
    res1 = bootstrap(db_session, password=test_password)
    assert res1["departments_created"] == 6
    assert res1["users_created"] == 15

    # Verify counts in DB
    assert db_session.query(Department).count() == 6
    assert db_session.query(User).count() == 15

    # Run 2: Second bootstrap (idempotency check)
    res2 = bootstrap(db_session, password=test_password)
    assert res2["departments_created"] == 0
    assert res2["users_created"] == 0
    assert res2["users_updated"] == 15

    # Counts must remain unchanged
    assert db_session.query(Department).count() == 6
    assert db_session.query(User).count() == 15

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
        ("requester.finance@demo-holdings.example", ["requester"], Decimal("0.00"), "Finance"),
        ("manager.finance@demo-holdings.example", ["manager"], Decimal("50000.00"), "Finance"),
        ("requester.hr@demo-holdings.example", ["requester"], Decimal("0.00"), "HR"),
        ("manager.hr@demo-holdings.example", ["manager"], Decimal("50000.00"), "HR"),
        ("requester.ops@demo-holdings.example", ["requester"], Decimal("0.00"), "Operations"),
        ("manager.ops@demo-holdings.example", ["manager"], Decimal("50000.00"), "Operations"),
        ("requester.projects@demo-holdings.example", ["requester"], Decimal("0.00"), "Projects"),
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


@pytest.mark.integration
def test_bootstrap_over_original_seed_adds_only_new_rows(db_session: Session) -> None:
    test_password = "SecureDemoPassword123!"

    # Clean up to guarantee fresh start
    db_session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_no_update_delete"))
    db_session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_no_truncate"))
    db_session.execute(text("TRUNCATE audit_log RESTART IDENTITY CASCADE"))
    db_session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_no_update_delete"))
    db_session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_no_truncate"))
    db_session.execute(text("DELETE FROM match_exceptions"))
    db_session.execute(text("DELETE FROM match_lines"))
    db_session.execute(text("DELETE FROM matches"))
    db_session.execute(text("DELETE FROM outbox"))
    db_session.execute(text("DELETE FROM approval_steps"))
    db_session.execute(text("DELETE FROM po_lines"))
    db_session.execute(text("DELETE FROM purchase_orders"))
    db_session.execute(text("DELETE FROM pr_lines"))
    db_session.execute(text("DELETE FROM purchase_requests"))
    db_session.execute(text("DELETE FROM user_roles"))
    db_session.execute(text("DELETE FROM users"))
    db_session.execute(text("DELETE FROM departments"))
    db_session.commit()

    # Pre-seed original 3 departments only
    orig_depts = ["Facilities", "IT", "Projects"]
    orig_dept_map: dict[str, Department] = {}
    for d_name in orig_depts:
        d = Department(name=d_name)
        db_session.add(d)
        db_session.flush()
        orig_dept_map[d_name] = d

    # Pre-seed original 8 users only
    from app.core.models import UserRole
    from app.core.security import hash_password

    orig_users_data = [
        (
            "requester.fac@demo-holdings.example",
            "Fatima Demo-Requester",
            "Facilities",
            ["requester"],
            Decimal("0.00"),
        ),
        (
            "requester.it@demo-holdings.example",
            "Omar Demo-Requester",
            "IT",
            ["requester"],
            Decimal("0.00"),
        ),
        (
            "buyer1@demo-holdings.example",
            "Tariq Demo-Buyer",
            "Facilities",
            ["buyer"],
            Decimal("0.00"),
        ),
        ("buyer2@demo-holdings.example", "Sara Demo-Buyer", "IT", ["buyer"], Decimal("0.00")),
        (
            "manager.facilities@demo-holdings.example",
            "Mariam Demo-Manager",
            "Facilities",
            ["manager"],
            Decimal("50000.00"),
        ),
        (
            "manager.it@demo-holdings.example",
            "Yousef Demo-Manager",
            "IT",
            ["manager"],
            Decimal("50000.00"),
        ),
        (
            "manager.projects@demo-holdings.example",
            "Khalid Demo-Manager",
            "Projects",
            ["manager"],
            Decimal("250000.00"),
        ),
        ("admin@demo-holdings.example", "Aisha Demo-Admin", "IT", ["admin"], Decimal("0.00")),
    ]
    orig_user_ids: dict[str, uuid.UUID] = {}
    for email, dname, dept_name, roles, limit in orig_users_data:
        u = User(
            email=email,
            display_name=dname,
            department_id=orig_dept_map[dept_name].id,
            approval_limit_aed=limit,
            is_demo=True,
            active=True,
            password_hash=hash_password(test_password),
        )
        db_session.add(u)
        db_session.flush()
        orig_user_ids[email] = u.id
        for r in roles:
            db_session.add(UserRole(user_id=u.id, role=r))
    db_session.commit()

    # Pre-state asserts
    assert db_session.query(Department).count() == 3
    assert db_session.query(User).count() == 8

    # Run bootstrap with the 6 departments and 15 demo users
    res = bootstrap(db_session, password=test_password)

    # Must insert ONLY the 3 new departments and 7 new users
    assert res["departments_created"] == 3
    assert res["users_created"] == 7
    assert res["users_updated"] == 8

    # Totals are now 6 and 15
    assert db_session.query(Department).count() == 6
    assert db_session.query(User).count() == 15

    # Original users must retain their original IDs and attributes
    for email, dname, dept_name, roles, limit in orig_users_data:
        db_u = db_session.query(User).filter(User.email == email).first()
        assert db_u is not None
        assert db_u.id == orig_user_ids[email]
        assert db_u.display_name == dname
        assert db_u.department.name == dept_name
        assert db_u.approval_limit_aed == limit

    # Third run inserts nothing
    res3 = bootstrap(db_session, password=test_password)
    assert res3["departments_created"] == 0
    assert res3["users_created"] == 0
    assert res3["users_updated"] == 15
