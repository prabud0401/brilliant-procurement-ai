import os
import sys
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.audit.service import record as record_audit
from app.core.config import settings
from app.core.database import SessionLocal, get_migrator_engine
from app.core.models import Department, User, UserRole
from app.core.security import hash_password

DEPARTMENTS = ["Facilities", "IT", "Projects"]

DEMO_USERS: list[dict[str, Any]] = [
    {
        "email": "requester.fac@demo-holdings.example",
        "display_name": "Fatima Al-Nuaimi",
        "department": "Facilities",
        "roles": ["requester"],
        "approval_limit_aed": Decimal("0.00"),
    },
    {
        "email": "requester.it@demo-holdings.example",
        "display_name": "Zayed Al-Hashimi",
        "department": "IT",
        "roles": ["requester"],
        "approval_limit_aed": Decimal("0.00"),
    },
    {
        "email": "buyer1@demo-holdings.example",
        "display_name": "Tariq Mansoor",
        "department": "Facilities",
        "roles": ["buyer"],
        "approval_limit_aed": Decimal("0.00"),
    },
    {
        "email": "buyer2@demo-holdings.example",
        "display_name": "Sara Al-Zaabi",
        "department": "IT",
        "roles": ["buyer"],
        "approval_limit_aed": Decimal("0.00"),
    },
    {
        "email": "manager.facilities@demo-holdings.example",
        "display_name": "Mariam Al-Khouri",
        "department": "Facilities",
        "roles": ["manager"],
        "approval_limit_aed": Decimal("50000.00"),
    },
    {
        "email": "manager.projects@demo-holdings.example",
        "display_name": "Rashid Al-Maktoum",
        "department": "Projects",
        "roles": ["manager"],
        "approval_limit_aed": Decimal("250000.00"),
    },
    {
        "email": "admin@demo-holdings.example",
        "display_name": "System Admin",
        "department": "IT",
        "roles": ["admin"],
        "approval_limit_aed": Decimal("0.00"),
    },
]


def bootstrap(db: Session, password: str | None = None) -> dict[str, int]:
    """Idempotently bootstrap demo departments and accounts."""
    pwd = password or settings.DEMO_USER_PASSWORD or os.environ.get("DEMO_USER_PASSWORD")
    if not pwd:
        raise ValueError("DEMO_USER_PASSWORD must be set to run bootstrap.")

    pw_hash = hash_password(pwd)

    # 1. Departments
    dept_map: dict[str, Department] = {}
    depts_created = 0
    for name in DEPARTMENTS:
        dept = db.query(Department).filter(Department.name == name).first()
        if not dept:
            dept = Department(name=name)
            db.add(dept)
            db.flush()
            depts_created += 1
            record_audit(
                session=db,
                actor=None,
                action="department.bootstrapped",
                entity_type="department",
                entity_id=dept.id,
                after={"name": dept.name},
                reason="System bootstrap",
            )
        dept_map[name] = dept

    # 2. Users and Roles
    users_created = 0
    users_updated = 0
    for u_data in DEMO_USERS:
        email = str(u_data["email"])
        dept_obj = dept_map[u_data["department"]]
        roles = list(u_data["roles"])
        limit_aed = Decimal(str(u_data["approval_limit_aed"]))

        user = db.query(User).filter(User.email == email).first()
        is_new = False
        if not user:
            is_new = True
            user = User(
                email=email,
                display_name=u_data["display_name"],
                department_id=dept_obj.id,
                approval_limit_aed=limit_aed,
                is_demo=True,
                active=True,
                password_hash=pw_hash,
            )
            db.add(user)
            db.flush()
            users_created += 1
        else:
            user.display_name = u_data["display_name"]
            user.department_id = dept_obj.id
            user.approval_limit_aed = limit_aed
            user.is_demo = True
            user.active = True
            user.password_hash = pw_hash
            db.flush()
            users_updated += 1

        # Synchronize roles
        existing_roles = {r.role for r in user.roles}
        target_roles = set(roles)

        # Remove deleted
        for r in list(user.roles):
            if r.role not in target_roles:
                db.delete(r)

        # Add missing
        for role_name in target_roles - existing_roles:
            db.add(UserRole(user_id=user.id, role=role_name))
        db.flush()

        record_audit(
            session=db,
            actor=None,
            action="user.bootstrapped",
            entity_type="user",
            entity_id=user.id,
            after={
                "email": user.email,
                "roles": roles,
                "department": dept_obj.name,
                "approval_limit_aed": str(limit_aed),
                "is_new": is_new,
            },
            reason="System bootstrap",
        )

    db.commit()
    return {
        "departments_created": depts_created,
        "users_created": users_created,
        "users_updated": users_updated,
    }


def main() -> None:
    pwd = settings.DEMO_USER_PASSWORD or os.environ.get("DEMO_USER_PASSWORD")
    if not pwd:
        sys.stderr.write("ERROR: DEMO_USER_PASSWORD environment variable must be set.\n")
        sys.exit(1)

    try:
        session = get_migrator_engine()
    except Exception:
        session = SessionLocal()

    try:
        results = bootstrap(session, pwd)
        print(
            f"Bootstrap completed successfully: "
            f"{results['departments_created']} departments created, "
            f"{results['users_created']} users created, "
            f"{results['users_updated']} users updated."
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
