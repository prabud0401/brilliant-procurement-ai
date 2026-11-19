from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap
from app.core.models import AuditLog, User
from app.main import app


@pytest.mark.integration
def test_api_auth_and_audit_lifecycle(db_session: Session) -> None:
    """Integration test verifying auth and audit lifecycle with real Postgres:

    - Bootstrap accounts
    - Log in as each role with password
    - GET /api/v1/me returns right roles and department
    - Wrong password -> 401 and an audit entry 'auth.login_failed'
    - Audit list scope: Requester sees only own entries, Manager only own department,
      Buyer business entries, Admin all
    - Requester/Buyer/Manager get 403 on export.csv and Admin gets CSV
    - /audit/verify true for Admin
    """
    test_password = "SecureIntegrationPassword123!"

    # 1. Clean existing state
    db_session.execute(text("DELETE FROM user_roles"))
    db_session.execute(text("DELETE FROM users"))
    db_session.execute(text("DELETE FROM departments"))
    db_session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_no_truncate"))
    db_session.execute(text("TRUNCATE audit_log RESTART IDENTITY"))
    db_session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_no_truncate"))
    db_session.commit()

    # 2. Bootstrap demo accounts
    boot_res = bootstrap(db_session, password=test_password)
    assert boot_res["users_created"] == 7
    assert boot_res["departments_created"] == 3

    user_req_fac = (
        db_session.query(User).filter(User.email == "requester.fac@demo-holdings.example").one()
    )
    user_req_it = (
        db_session.query(User).filter(User.email == "requester.it@demo-holdings.example").one()
    )
    user_buyer1 = db_session.query(User).filter(User.email == "buyer1@demo-holdings.example").one()
    user_buyer2 = db_session.query(User).filter(User.email == "buyer2@demo-holdings.example").one()
    user_mgr_fac = (
        db_session.query(User)
        .filter(User.email == "manager.facilities@demo-holdings.example")
        .one()
    )
    user_mgr_proj = (
        db_session.query(User).filter(User.email == "manager.projects@demo-holdings.example").one()
    )
    user_admin = db_session.query(User).filter(User.email == "admin@demo-holdings.example").one()

    client = TestClient(app)

    # 3. Wrong password -> 401 and audit entry 'auth.login_failed'
    bad_login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": user_req_fac.email, "password": "wrong_password_attempt"},
    )
    assert bad_login_resp.status_code == 401
    assert bad_login_resp.json()["code"] == "INVALID_CREDENTIALS"

    failed_audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "auth.login_failed")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert failed_audit is not None
    assert failed_audit.entity_type == "auth"
    assert failed_audit.entity_id == user_req_fac.id
    assert failed_audit.after == {"email": user_req_fac.email}

    # 4. Log in as each role and verify GET /api/v1/me
    demo_accounts = [
        (user_req_fac.email, ["requester"], "Facilities", Decimal("0.00")),
        (user_req_it.email, ["requester"], "IT", Decimal("0.00")),
        (user_buyer1.email, ["buyer"], "Facilities", Decimal("0.00")),
        (user_buyer2.email, ["buyer"], "IT", Decimal("0.00")),
        (user_mgr_fac.email, ["manager"], "Facilities", Decimal("50000.00")),
        (user_mgr_proj.email, ["manager"], "Projects", Decimal("250000.00")),
        (user_admin.email, ["admin"], "IT", Decimal("0.00")),
    ]

    tokens: dict[str, str] = {}
    for email, expected_roles, expected_dept, expected_limit in demo_accounts:
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": test_password},
        )
        assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
        token = resp.json()["access_token"]
        tokens[email] = token

        me_resp = client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200, f"/me failed for {email}: {me_resp.text}"
        me_data = me_resp.json()
        assert me_data["email"] == email
        assert me_data["roles"] == expected_roles
        assert me_data["department_name"] == expected_dept
        assert Decimal(str(me_data["approval_limit_aed"])) == expected_limit
        assert me_data["is_demo"] is True
        assert me_data["active"] is True

    token_req_fac = tokens[user_req_fac.email]
    token_req_it = tokens[user_req_it.email]
    token_buyer1 = tokens[user_buyer1.email]
    token_mgr_fac = tokens[user_mgr_fac.email]
    token_admin = tokens[user_admin.email]

    # 5. Audit list scope
    # Requester: sees ONLY own entries
    req_resp = client.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {token_req_fac}"},
    )
    assert req_resp.status_code == 200
    req_items = req_resp.json()["items"]
    assert len(req_items) > 0
    for item in req_items:
        assert item["actor_id"] == str(user_req_fac.id)

    # Manager: sees ONLY own department entries (Facilities: req_fac, buyer1, mgr_fac)
    mgr_resp = client.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {token_mgr_fac}"},
    )
    assert mgr_resp.status_code == 200
    mgr_items = mgr_resp.json()["items"]
    assert len(mgr_items) > len(req_items)
    facilities_actors = {str(user_req_fac.id), str(user_buyer1.id), str(user_mgr_fac.id)}
    for item in mgr_items:
        if item["actor_id"] is not None:
            assert item["actor_id"] in facilities_actors
    assert not any(i["actor_id"] == str(user_req_it.id) for i in mgr_items)
    assert not any(i["actor_id"] == str(user_admin.id) for i in mgr_items)

    # Buyer: sees all business entries across departments
    buyer_resp = client.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {token_buyer1}"},
    )
    assert buyer_resp.status_code == 200
    buyer_items = buyer_resp.json()["items"]
    buyer_actor_ids = {i["actor_id"] for i in buyer_items if i["actor_id"]}
    assert str(user_req_fac.id) in buyer_actor_ids
    assert str(user_req_it.id) in buyer_actor_ids
    assert str(user_mgr_fac.id) in buyer_actor_ids

    # Admin: sees ALL entries
    admin_resp = client.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert admin_resp.status_code == 200
    admin_items = admin_resp.json()["items"]
    assert len(admin_items) >= len(buyer_items)
    assert any(i["action"] == "auth.login_failed" for i in admin_items)
    assert any(i["action"] == "department.bootstrapped" for i in admin_items)

    # 6. Audit export CSV: Requester/Buyer/Manager get 403, Admin gets CSV
    for role_name, r_tok in [
        ("Requester (Facilities)", token_req_fac),
        ("Requester (IT)", token_req_it),
        ("Buyer", token_buyer1),
        ("Manager", token_mgr_fac),
    ]:
        csv_resp = client.get(
            "/api/v1/audit/export.csv",
            headers={"Authorization": f"Bearer {r_tok}"},
        )
        assert csv_resp.status_code == 403, f"{role_name} expected 403, got {csv_resp.status_code}"
        assert csv_resp.json()["code"] == "FORBIDDEN"

    admin_csv_resp = client.get(
        "/api/v1/audit/export.csv",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert admin_csv_resp.status_code == 200
    assert admin_csv_resp.headers["content-type"].startswith("text/csv")
    assert "audit_export.csv" in admin_csv_resp.headers["content-disposition"]
    assert "id,occurred_at,actor_id" in admin_csv_resp.text
    assert "auth.login_success" in admin_csv_resp.text
    assert "auth.login_failed" in admin_csv_resp.text

    # 7. Audit verify chain: Admin gets 200 and valid=True, non-admins get 403
    for role_name, r_tok in [
        ("Requester (Facilities)", token_req_fac),
        ("Requester (IT)", token_req_it),
        ("Buyer", token_buyer1),
        ("Manager", token_mgr_fac),
    ]:
        v_resp = client.get(
            "/api/v1/audit/verify",
            headers={"Authorization": f"Bearer {r_tok}"},
        )
        assert v_resp.status_code == 403, f"{role_name} expected 403, got {v_resp.status_code}"

    admin_verify_resp = client.get(
        "/api/v1/audit/verify",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert admin_verify_resp.status_code == 200
    v_data = admin_verify_resp.json()
    assert v_data["valid"] is True
    assert v_data["count"] > 0
    assert v_data["error"] is None
