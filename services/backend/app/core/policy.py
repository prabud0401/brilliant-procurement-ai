import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, cast

from fastapi import Depends
from sqlalchemy import false, true
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.database import get_db
from app.core.errors import ProblemException
from app.core.models import AuditLog, Chunk, Document, PurchaseOrder, PurchaseRequest, User
from app.core.security import decode_access_token, extract_bearer_token


class Role(str, Enum):
    REQUESTER = "requester"
    BUYER = "buyer"
    MANAGER = "manager"
    ADMIN = "admin"


class ScopeRule(str, Enum):
    NONE = "none"
    OWN = "own"
    DEPT = "dept"
    ALL = "all"
    METADATA = "metadata"
    TIER_1_NOT_OWN = "tier 1, never own"
    WITHIN_LIMIT_NOT_OWN = "within limit, never own"
    POLICY = "policy"
    ESCALATED = "escalated"


# Capability table exactly mirroring Design 7.2
CAPABILITY_MATRIX: dict[str, dict[str, ScopeRule]] = {
    # Upload, re-extract: POST /documents, PATCH /documents/{id}, POST /documents/{id}/extract
    "document.upload_extract": {
        Role.REQUESTER: ScopeRule.OWN,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.NONE,
    },
    # View documents and extraction: GET /documents..., /extraction, /file
    "document.view": {
        Role.REQUESTER: ScopeRule.OWN,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.DEPT,
        Role.ADMIN: ScopeRule.METADATA,
    },
    # Review and confirm fields, link vendor, clear duplicate:
    # PATCH /fields, /lines; POST /confirm, /vendor, /not-duplicate
    "document.review": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.NONE,
    },
    # SharePoint import: /integrations/sharepoint/*
    "integration.sharepoint": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.NONE,
    },
    # Create and edit purchase requests: POST, PATCH /purchase-requests
    "pr.create_edit": {
        Role.REQUESTER: ScopeRule.ALL,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.ALL,
        Role.ADMIN: ScopeRule.NONE,
    },
    # Submit for approval: POST .../submit
    "pr.submit": {
        Role.REQUESTER: ScopeRule.OWN,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.NONE,
    },
    # Comparisons, weights, recommendation, override: /comparisons/* (write)
    "comparison.write": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.NONE,
    },
    # View comparison: GET /comparisons/{id}
    "comparison.view": {
        Role.REQUESTER: ScopeRule.OWN,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.DEPT,
        Role.ADMIN: ScopeRule.NONE,
    },
    # Create PO, push to Odoo: POST /purchase-orders, /push-to-odoo
    "po.create": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.NONE,
    },
    # Approve or reject: POST /approvals/{id}/decision
    "approval.decide": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.TIER_1_NOT_OWN,
        Role.MANAGER: ScopeRule.WITHIN_LIMIT_NOT_OWN,
        Role.ADMIN: ScopeRule.NONE,
    },
    # Run match, resolve exceptions: POST /matches, /exceptions/{id}/resolve
    "match.resolve": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.POLICY,
        Role.MANAGER: ScopeRule.ESCALATED,
        Role.ADMIN: ScopeRule.NONE,
    },
    # Q&A: POST /qa/ask
    "qa.ask": {
        Role.REQUESTER: ScopeRule.OWN,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.DEPT,
        Role.ADMIN: ScopeRule.NONE,
    },
    # View audit: GET /audit
    "audit.view": {
        Role.REQUESTER: ScopeRule.OWN,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.DEPT,
        Role.ADMIN: ScopeRule.ALL,
    },
    # Export audit: GET /audit/export.csv
    "audit.export": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.NONE,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.ALL,
    },
    # Users, thresholds, tolerances, integrations, retention, metrics: /admin/*, PUT /settings/*
    "admin.manage": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.NONE,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.ALL,
    },
}


@dataclass
class Principal:
    id: uuid.UUID
    email: str
    display_name: str
    roles: list[str]
    department_id: uuid.UUID | None
    department_name: str | None
    approval_limit_aed: Decimal
    is_demo: bool = False
    active: bool = True


def get_effective_scope(principal: Principal, capability: str) -> ScopeRule:
    cap_rules = CAPABILITY_MATRIX.get(capability)
    if not cap_rules:
        return ScopeRule.NONE

    user_rules = [cap_rules.get(r, ScopeRule.NONE) for r in principal.roles if r in cap_rules]
    if not user_rules:
        return ScopeRule.NONE

    # Hierarchy: ALL > DEPT > OWN > METADATA / specific rules > NONE
    if ScopeRule.ALL in user_rules:
        return ScopeRule.ALL
    if ScopeRule.DEPT in user_rules:
        return ScopeRule.DEPT
    if ScopeRule.OWN in user_rules:
        return ScopeRule.OWN
    if ScopeRule.METADATA in user_rules:
        return ScopeRule.METADATA
    if ScopeRule.TIER_1_NOT_OWN in user_rules:
        return ScopeRule.TIER_1_NOT_OWN
    if ScopeRule.WITHIN_LIMIT_NOT_OWN in user_rules:
        return ScopeRule.WITHIN_LIMIT_NOT_OWN
    if ScopeRule.POLICY in user_rules:
        return ScopeRule.POLICY
    if ScopeRule.ESCALATED in user_rules:
        return ScopeRule.ESCALATED

    return ScopeRule.NONE


def get_current_principal(
    token: str = Depends(extract_bearer_token),
    db: Session = Depends(get_db),
) -> Principal:
    payload = decode_access_token(token)
    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise ProblemException(
            status_code=401,
            code="INVALID_TOKEN",
            title="Unauthorized",
            detail="Token sub is not a valid UUID",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.active:
        raise ProblemException(
            status_code=401,
            code="USER_INACTIVE",
            title="Unauthorized",
            detail="User account is inactive or not found",
        )

    roles = [r.role for r in user.roles]
    dept_name = user.department.name if user.department else None

    return Principal(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=roles,
        department_id=user.department_id,
        department_name=dept_name,
        approval_limit_aed=user.approval_limit_aed,
        is_demo=user.is_demo,
        active=user.active,
    )


def require(capability: str) -> Callable[[Principal], Principal]:
    def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        scope = get_effective_scope(principal, capability)
        if scope == ScopeRule.NONE:
            raise ProblemException(
                status_code=403,
                code="FORBIDDEN",
                title="Forbidden",
                detail=f"Principal lacks permission for capability '{capability}'",
            )
        return principal

    return dependency


def scope_filter(
    principal: Principal,
    capability: str,
    model: Any,
) -> ColumnElement[bool]:
    """Helper to return a SQLAlchemy filter condition enforcing record-level scope."""
    scope = get_effective_scope(principal, capability)

    if scope == ScopeRule.ALL or scope == ScopeRule.METADATA:
        return true()

    if scope == ScopeRule.NONE:
        return false()

    # Scope for AuditLog
    if model is AuditLog:
        if scope == ScopeRule.OWN:
            return AuditLog.actor_id == principal.id
        if scope == ScopeRule.DEPT:
            if not principal.department_id:
                return AuditLog.actor_id == principal.id
            return AuditLog.actor_id.in_(
                User.__table__.select()
                .with_only_columns(User.id)
                .where(User.department_id == principal.department_id)
            )

    # Scopes for Document
    if model is Document:
        if scope == ScopeRule.OWN:
            return Document.owner_id == principal.id
        if scope == ScopeRule.DEPT:
            if not principal.department_id:
                return Document.owner_id == principal.id
            return Document.department_id == principal.department_id

    # Scopes for Chunk
    if model is Chunk:
        if scope == ScopeRule.OWN:
            return Chunk.owner_id == principal.id
        if scope == ScopeRule.DEPT:
            if not principal.department_id:
                return Chunk.owner_id == principal.id
            return Chunk.department_id == principal.department_id

    # Scopes for PurchaseRequest
    if model is PurchaseRequest:
        if scope == ScopeRule.OWN:
            return PurchaseRequest.requester_id == principal.id
        if scope == ScopeRule.DEPT:
            if not principal.department_id:
                return PurchaseRequest.requester_id == principal.id
            return PurchaseRequest.department_id == principal.department_id

    # Scopes for PurchaseOrder
    if model is PurchaseOrder:
        if scope == ScopeRule.OWN:
            return PurchaseOrder.created_by == principal.id
        if scope == ScopeRule.DEPT:
            if not principal.department_id:
                return PurchaseOrder.created_by == principal.id
            return PurchaseOrder.department_id == principal.department_id

    # Generic fallback
    if scope == ScopeRule.OWN:
        if hasattr(model, "owner_id"):
            return cast(ColumnElement[bool], getattr(model, "owner_id") == principal.id)
        if hasattr(model, "created_by"):
            return cast(ColumnElement[bool], getattr(model, "created_by") == principal.id)
        if hasattr(model, "user_id"):
            return cast(ColumnElement[bool], getattr(model, "user_id") == principal.id)
    elif scope == ScopeRule.DEPT:
        if hasattr(model, "department_id") and principal.department_id:
            return cast(
                ColumnElement[bool],
                getattr(model, "department_id") == principal.department_id,
            )

    return false()
