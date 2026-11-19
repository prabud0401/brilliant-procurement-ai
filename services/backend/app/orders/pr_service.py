import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.approvals.routing import build_approval_steps
from app.audit.service import record as record_audit
from app.core.errors import ProblemException
from app.core.models import ApprovalStep, PRLine, PurchaseRequest, User
from app.core.policy import Principal
from app.orders.schemas import PRCreateRequest, PRResponse, PRUpdateRequest


def _generate_pr_number(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    suffix = uuid.uuid4().hex[:6].upper()
    return f"PR-{year}-{suffix}"


def _get_current_approver(db: Session, pr_id: uuid.UUID) -> tuple[uuid.UUID | None, str | None]:
    step = (
        db.query(ApprovalStep)
        .filter(
            ApprovalStep.subject_type == "pr",
            ApprovalStep.subject_id == pr_id,
            ApprovalStep.status == "pending",
        )
        .order_by(ApprovalStep.sequence)
        .first()
    )
    if not step or not step.assigned_to:
        return None, None
    user = db.query(User).filter(User.id == step.assigned_to).first()
    return step.assigned_to, user.display_name if user else None


def create_pr(db: Session, body: PRCreateRequest, principal: Principal) -> PRResponse:
    dept_id = body.department_id or principal.department_id
    if not dept_id:
        raise ProblemException(
            status_code=422,
            code="DEPARTMENT_REQUIRED",
            title="Unprocessable Entity",
            detail="Department is required to create a purchase request",
        )

    number = _generate_pr_number(db)
    total = sum((line.qty * line.est_unit_price for line in body.lines), Decimal("0.00"))

    pr = PurchaseRequest(
        number=number,
        requester_id=principal.id,
        department_id=dept_id,
        title=body.title.strip(),
        status="draft",
        total_aed=total,
        currency="AED",
        created_by=principal.id,
    )
    db.add(pr)
    db.flush()

    for line in body.lines:
        pr_line = PRLine(
            pr_id=pr.id,
            product_id=line.product_id,
            description=line.description.strip(),
            qty=line.qty,
            uom=line.uom,
            est_unit_price=line.est_unit_price,
            created_by=principal.id,
        )
        db.add(pr_line)

    db.flush()

    record_audit(
        session=db,
        actor=principal,
        action="pr.created",
        entity_type="purchase_request",
        entity_id=pr.id,
        after={
            "number": pr.number,
            "title": pr.title,
            "total_aed": str(pr.total_aed),
            "lines_count": len(body.lines),
        },
        reason="Purchase request created in draft",
    )
    db.commit()

    return PRResponse.model_validate(pr)


def list_prs(
    db: Session,
    principal: Principal,
    status_filter: str | None = None,
) -> list[PRResponse]:
    query = db.query(PurchaseRequest)

    if "buyer" in principal.roles:
        pass
    elif "manager" in principal.roles:
        if principal.department_id:
            query = query.filter(PurchaseRequest.department_id == principal.department_id)
        else:
            query = query.filter(PurchaseRequest.requester_id == principal.id)
    elif "requester" in principal.roles:
        query = query.filter(PurchaseRequest.requester_id == principal.id)
    else:
        from sqlalchemy import false

        query = query.filter(false())

    if status_filter:
        query = query.filter(PurchaseRequest.status == status_filter.strip().lower())

    prs = query.order_by(PurchaseRequest.created_at.desc()).all()
    results: list[PRResponse] = []
    for pr in prs:
        approver_id, approver_name = _get_current_approver(db, pr.id)
        resp = PRResponse.model_validate(pr)
        resp.current_approver_id = approver_id
        resp.current_approver = approver_name
        results.append(resp)
    return results


def get_pr(db: Session, pr_id: uuid.UUID, principal: Principal) -> PRResponse:
    pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == pr_id).first()
    if not pr:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail=f"Purchase request '{pr_id}' not found",
        )

    # Record-level scope check
    if "buyer" not in principal.roles and "admin" not in principal.roles:
        if "manager" in principal.roles:
            if pr.department_id != principal.department_id:
                raise ProblemException(
                    status_code=404,
                    code="NOT_FOUND",
                    title="Not Found",
                    detail="Purchase request not found in department scope",
                )
        else:
            if pr.requester_id != principal.id:
                raise ProblemException(
                    status_code=404,
                    code="NOT_FOUND",
                    title="Not Found",
                    detail="Purchase request not found in owner scope",
                )

    approver_id, approver_name = _get_current_approver(db, pr.id)
    resp = PRResponse.model_validate(pr)
    resp.current_approver_id = approver_id
    resp.current_approver = approver_name
    return resp


def update_pr(
    db: Session,
    pr_id: uuid.UUID,
    body: PRUpdateRequest,
    principal: Principal,
) -> PRResponse:
    pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == pr_id).first()
    if not pr:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="PR not found",
        )

    if pr.requester_id != principal.id:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Only the creator can edit this purchase request",
        )

    if pr.status != "draft":
        raise ProblemException(
            status_code=409,
            code="PR_NOT_DRAFT",
            title="Conflict",
            detail="Only purchase requests in draft status can be edited",
        )

    old_val: dict[str, Any] = {"title": pr.title, "total_aed": str(pr.total_aed)}

    if body.title is not None:
        pr.title = body.title.strip()
    if body.department_id is not None:
        pr.department_id = body.department_id

    if body.lines is not None:
        db.query(PRLine).filter(PRLine.pr_id == pr.id).delete()
        total = sum(
            (line_item.qty * line_item.est_unit_price for line_item in body.lines),
            Decimal("0.00"),
        )
        pr.total_aed = total
        for line in body.lines:
            pr_line = PRLine(
                pr_id=pr.id,
                product_id=line.product_id,
                description=line.description.strip(),
                qty=line.qty,
                uom=line.uom,
                est_unit_price=line.est_unit_price,
                created_by=principal.id,
            )
            db.add(pr_line)

    pr.updated_at = datetime.now(timezone.utc)
    db.flush()

    record_audit(
        session=db,
        actor=principal,
        action="pr.updated",
        entity_type="purchase_request",
        entity_id=pr.id,
        before=old_val,
        after={"title": pr.title, "total_aed": str(pr.total_aed)},
        reason="Purchase request updated",
    )
    db.commit()

    return PRResponse.model_validate(pr)


def submit_pr(db: Session, pr_id: uuid.UUID, principal: Principal) -> PRResponse:
    pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == pr_id).first()
    if not pr:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="PR not found",
        )

    # Creator check (R, B)
    if pr.requester_id != principal.id and "buyer" not in principal.roles:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Only the creator or a Buyer can submit this purchase request",
        )

    if pr.status != "draft":
        raise ProblemException(
            status_code=409,
            code="PR_NOT_DRAFT",
            title="Conflict",
            detail=f"Cannot submit purchase request in status '{pr.status}'",
        )

    # Build routing steps
    steps, rule_snapshot = build_approval_steps(
        db=db,
        subject_type="pr",
        subject_id=pr.id,
        total_aed=pr.total_aed,
        department_id=pr.department_id,
        creator_id=pr.requester_id,
    )

    pr.status = "submitted"
    pr.submitted_at = datetime.now(timezone.utc)
    pr.rule_snapshot = rule_snapshot
    pr.updated_at = datetime.now(timezone.utc)

    db.flush()

    record_audit(
        session=db,
        actor=principal,
        action="pr.submitted",
        entity_type="purchase_request",
        entity_id=pr.id,
        before={"status": "draft"},
        after={"status": "submitted", "tier": rule_snapshot.get("tier"), "steps": len(steps)},
        reason="Purchase request submitted for approval",
    )
    db.commit()

    approver_id, approver_name = _get_current_approver(db, pr.id)
    resp = PRResponse.model_validate(pr)
    resp.current_approver_id = approver_id
    resp.current_approver = approver_name
    return resp
