import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.admin.schemas import (
    AdminDepartmentResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    IntegrationStatusItem,
    RetentionSettingsResponse,
    RetentionSettingsUpdateRequest,
    SettingHistoryItem,
)
from app.audit.service import record as record_audit
from app.core.errors import ProblemException
from app.core.models import AuditLog, Department, User, UserRole
from app.core.policy import Principal
from app.integrations import (
    get_identity_adapter,
    get_integrations_mode,
    get_odoo_adapter,
    get_power_automate_adapter,
    get_sharepoint_adapter,
)
from app.settings_api.service import KEY_ALIASES, get_setting, update_setting

VALID_ROLES = {"requester", "buyer", "manager", "admin"}
BUSINESS_ROLES = {"requester", "buyer", "manager"}


def list_users(db: Session) -> list[AdminUserResponse]:
    users = db.query(User).order_by(User.email.asc()).all()
    results: list[AdminUserResponse] = []
    for u in users:
        role_names = [r.role for r in u.roles]
        dept_name = u.department.name if u.department else None
        results.append(
            AdminUserResponse(
                id=u.id,
                email=u.email,
                display_name=u.display_name,
                roles=role_names,
                department_id=u.department_id,
                department_name=dept_name,
                approval_limit_aed=u.approval_limit_aed,
                active=u.active,
                is_demo=u.is_demo,
                created_at=u.created_at,
                updated_at=u.updated_at,
            )
        )
    return results


def get_user(db: Session, user_id: uuid.UUID) -> AdminUserResponse:
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise ProblemException(
            status_code=404,
            code="USER_NOT_FOUND",
            title="Not Found",
            detail=f"User with ID '{user_id}' was not found.",
        )
    role_names = [r.role for r in u.roles]
    dept_name = u.department.name if u.department else None
    return AdminUserResponse(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        roles=role_names,
        department_id=u.department_id,
        department_name=dept_name,
        approval_limit_aed=u.approval_limit_aed,
        active=u.active,
        is_demo=u.is_demo,
        created_at=u.created_at,
        updated_at=u.updated_at,
    )


def list_departments(db: Session) -> list[AdminDepartmentResponse]:
    depts = db.query(Department).order_by(Department.name.asc()).all()
    return [AdminDepartmentResponse.model_validate(d) for d in depts]


def update_user(
    db: Session,
    user_id: uuid.UUID,
    body: AdminUserUpdateRequest,
    actor: Principal,
) -> AdminUserResponse:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ProblemException(
            status_code=404,
            code="USER_NOT_FOUND",
            title="Not Found",
            detail=f"User with ID '{user_id}' was not found.",
        )

    current_roles = {r.role for r in user.roles}
    before_state: dict[str, Any] = {
        "roles": sorted(list(current_roles)),
        "approval_limit_aed": str(user.approval_limit_aed),
        "department_id": str(user.department_id) if user.department_id else None,
        "active": user.active,
    }

    # Validate roles if changing
    if body.roles is not None:
        cleaned_roles = {r.strip().lower() for r in body.roles}
        invalid = cleaned_roles - VALID_ROLES
        if invalid:
            raise ProblemException(
                status_code=422,
                code="INVALID_ROLE",
                title="Unprocessable Entity",
                detail=f"Invalid roles specified: {', '.join(sorted(invalid))}",
            )

        # Segregation & Audit Rule: Admin cannot grant itself business roles silently.
        # An audit entry with reason is strictly required.
        is_self = actor.id == user.id
        target_is_admin = "admin" in current_roles or "admin" in cleaned_roles
        new_business_roles = (cleaned_roles - current_roles) & BUSINESS_ROLES

        if (is_self or target_is_admin) and new_business_roles:
            if not body.reason or len(body.reason.strip()) < 10:
                raise ProblemException(
                    status_code=400,
                    code="REASON_REQUIRED",
                    title="Reason Required",
                    detail=(
                        "Admin cannot grant business roles silently. "
                        "An audit reason of at least 10 characters is required."
                    ),
                )

        # Apply roles update
        db.query(UserRole).filter(UserRole.user_id == user.id).delete()
        for role_name in cleaned_roles:
            db.add(UserRole(user_id=user.id, role=role_name))

    if body.approval_limit_aed is not None:
        user.approval_limit_aed = body.approval_limit_aed

    if body.department_id is not None:
        dept = db.query(Department).filter(Department.id == body.department_id).first()
        if not dept:
            raise ProblemException(
                status_code=422,
                code="DEPARTMENT_NOT_FOUND",
                title="Unprocessable Entity",
                detail=f"Department '{body.department_id}' not found.",
            )
        user.department_id = body.department_id

    if body.active is not None:
        user.active = body.active

    user.updated_at = datetime.now(timezone.utc)
    db.flush()

    # Re-read new state
    new_roles = (
        sorted(list(cleaned_roles))
        if body.roles is not None
        else sorted([r.role for r in user.roles])
    )
    after_state: dict[str, Any] = {
        "roles": new_roles,
        "approval_limit_aed": str(user.approval_limit_aed),
        "department_id": str(user.department_id) if user.department_id else None,
        "active": user.active,
    }

    audit_reason = (
        body.reason.strip() if body.reason and body.reason.strip() else "Admin updated user"
    )

    record_audit(
        session=db,
        actor=actor,
        action="admin.user_updated",
        entity_type="user",
        entity_id=user.id,
        before=before_state,
        after=after_state,
        reason=audit_reason,
    )
    db.commit()

    dept_name = user.department.name if user.department else None
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=new_roles,
        department_id=user.department_id,
        department_name=dept_name,
        approval_limit_aed=user.approval_limit_aed,
        active=user.active,
        is_demo=user.is_demo,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def list_integrations() -> list[IntegrationStatusItem]:
    mode = get_integrations_mode()
    odoo = get_odoo_adapter()
    sharepoint = get_sharepoint_adapter()
    power_automate = get_power_automate_adapter()
    identity = get_identity_adapter()

    return [
        IntegrationStatusItem(
            adapter="odoo",
            name="Odoo ERP",
            mode=mode,
            label=odoo.name,
        ),
        IntegrationStatusItem(
            adapter="sharepoint",
            name="Microsoft SharePoint",
            mode=mode,
            label=sharepoint.name,
        ),
        IntegrationStatusItem(
            adapter="power_automate",
            name="Power Automate & Teams",
            mode=mode,
            label=power_automate.name,
        ),
        IntegrationStatusItem(
            adapter="identity",
            name="Microsoft Entra ID",
            mode=mode,
            label=identity.name,
        ),
    ]


def get_setting_history(db: Session, key: str) -> list[SettingHistoryItem]:
    canonical_key = KEY_ALIASES.get(key.strip().lower(), key.strip().lower())

    logs = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "setting")
        .order_by(AuditLog.id.desc())
        .limit(50)
        .all()
    )

    matching_items: list[SettingHistoryItem] = []
    for log in logs:
        after_dict = log.after if isinstance(log.after, dict) else {}
        before_dict = log.before if isinstance(log.before, dict) else {}

        log_key = after_dict.get("key") or before_dict.get("key")
        if log_key == canonical_key or key == "all":
            actor_name = None
            if log.actor_id:
                u = db.query(User).filter(User.id == log.actor_id).first()
                if u:
                    actor_name = u.display_name

            matching_items.append(
                SettingHistoryItem(
                    id=log.id,
                    occurred_at=log.occurred_at,
                    actor_id=log.actor_id,
                    actor_name=actor_name,
                    action=log.action,
                    version=after_dict.get("version"),
                    value=after_dict.get("value"),
                    reason=log.reason,
                )
            )

    return matching_items


def get_retention_settings(db: Session) -> RetentionSettingsResponse:
    res = get_setting(db, "retention")
    val = res.get("value", {})
    if not isinstance(val, dict):
        val = {}
    return RetentionSettingsResponse(
        documents_retention_days=int(val.get("documents_retention_days", 30)),
        audit_retention_days=int(val.get("audit_retention_days", 365)),
    )


def update_retention_settings(
    db: Session,
    body: RetentionSettingsUpdateRequest,
    actor: Principal,
) -> RetentionSettingsResponse:
    current = get_retention_settings(db)
    new_doc_days = (
        body.documents_retention_days
        if body.documents_retention_days is not None
        else current.documents_retention_days
    )
    new_audit_days = (
        body.audit_retention_days
        if body.audit_retention_days is not None
        else current.audit_retention_days
    )

    val = {
        "documents_retention_days": new_doc_days,
        "audit_retention_days": new_audit_days,
    }
    update_setting(db, "retention", val, actor)
    return RetentionSettingsResponse(
        documents_retention_days=new_doc_days,
        audit_retention_days=new_audit_days,
    )
