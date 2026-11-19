import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.approvals.schemas import (
    ApprovalBundleResponse,
    EarlierDecision,
    InboxItemResponse,
)
from app.audit.service import record as record_audit
from app.core.errors import ProblemException
from app.core.models import (
    ApprovalStep,
    Comparison,
    Match,
    PurchaseOrder,
    PurchaseRequest,
    User,
)
from app.core.policy import Principal


def get_inbox(db: Session, principal: Principal) -> list[InboxItemResponse]:
    # Non-business roles (e.g. admin without buyer/manager) have no inbox
    if not any(r in ("buyer", "manager") for r in principal.roles):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Business role (Buyer or Manager) required to access inbox",
        )

    # 1. Fetch pending steps assigned to this principal
    steps = (
        db.query(ApprovalStep)
        .filter(
            ApprovalStep.assigned_to == principal.id,
            ApprovalStep.status == "pending",
        )
        .all()
    )

    items: list[InboxItemResponse] = []

    for step in steps:
        # Check sequencing: if there is an earlier step still pending for this subject, skip
        earlier_pending = (
            db.query(ApprovalStep)
            .filter(
                ApprovalStep.subject_type == step.subject_type,
                ApprovalStep.subject_id == step.subject_id,
                ApprovalStep.sequence < step.sequence,
                ApprovalStep.status == "pending",
            )
            .first()
        )
        if earlier_pending:
            continue

        if step.subject_type == "pr":
            pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == step.subject_id).first()
            if not pr:
                continue
            # SOD check: creator cannot approve own PR
            if pr.requester_id == principal.id:
                continue

            requester = db.query(User).filter(User.id == pr.requester_id).first()
            req_name = requester.display_name if requester else "Unknown"
            dept_name = requester.department.name if requester and requester.department else None

            items.append(
                InboxItemResponse(
                    step_id=step.id,
                    subject_type="pr",
                    subject_id=pr.id,
                    subject_number=pr.number,
                    title=pr.title,
                    total_aed=pr.total_aed,
                    requester_id=pr.requester_id,
                    requester_name=req_name,
                    department_id=pr.department_id,
                    department_name=dept_name,
                    tier=step.tier,
                    sequence=step.sequence,
                    created_at=step.created_at,
                )
            )
        elif step.subject_type == "po":
            po = db.query(PurchaseOrder).filter(PurchaseOrder.id == step.subject_id).first()
            if not po:
                continue
            # SOD check: creator cannot approve own PO
            if po.created_by == principal.id:
                continue

            creator = db.query(User).filter(User.id == po.created_by).first()
            creator_name = creator.display_name if creator else "Unknown"
            dept_name = creator.department.name if creator and creator.department else None

            items.append(
                InboxItemResponse(
                    step_id=step.id,
                    subject_type="po",
                    subject_id=po.id,
                    subject_number=po.number,
                    title=f"Purchase Order {po.number}",
                    total_aed=po.total,
                    requester_id=po.created_by,
                    requester_name=creator_name,
                    department_id=po.department_id,
                    department_name=dept_name,
                    tier=step.tier,
                    sequence=step.sequence,
                    created_at=step.created_at,
                )
            )

    return items


def get_approval_bundle(
    db: Session,
    step_id: uuid.UUID,
    principal: Principal,
) -> ApprovalBundleResponse:
    step = db.query(ApprovalStep).filter(ApprovalStep.id == step_id).first()
    if not step:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail=f"Approval step '{step_id}' not found",
        )

    # Get earlier decisions
    earlier_steps = (
        db.query(ApprovalStep)
        .filter(
            ApprovalStep.subject_type == step.subject_type,
            ApprovalStep.subject_id == step.subject_id,
            ApprovalStep.sequence < step.sequence,
        )
        .order_by(ApprovalStep.sequence)
        .all()
    )
    earlier_decisions: list[EarlierDecision] = []
    for s in earlier_steps:
        dec_user = db.query(User).filter(User.id == s.decided_by).first() if s.decided_by else None
        earlier_decisions.append(
            EarlierDecision(
                step_id=s.id,
                sequence=s.sequence,
                tier=s.tier,
                assigned_to=s.assigned_to,
                decided_by=s.decided_by,
                decided_by_name=dec_user.display_name if dec_user else None,
                status=s.status,
                comment=s.comment,
                decided_at=s.decided_at,
            )
        )

    subject_data: dict[str, Any] = {}
    comparison_data: dict[str, Any] | None = None
    match_data: dict[str, Any] | None = None

    if step.subject_type == "pr":
        pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == step.subject_id).first()
        if not pr:
            raise ProblemException(
                status_code=404,
                code="NOT_FOUND",
                title="Not Found",
                detail="Associated purchase request not found",
            )
        subject_data = {
            "id": str(pr.id),
            "number": pr.number,
            "title": pr.title,
            "status": pr.status,
            "total_aed": str(pr.total_aed),
            "currency": pr.currency,
            "requester_id": str(pr.requester_id),
            "department_id": str(pr.department_id),
            "lines": [
                {
                    "id": str(line.id),
                    "description": line.description,
                    "qty": str(line.qty),
                    "uom": line.uom,
                    "est_unit_price": str(line.est_unit_price),
                }
                for line in pr.lines
            ],
        }

        # Check for comparison
        comp = (
            db.query(Comparison)
            .filter(Comparison.pr_id == pr.id)
            .order_by(Comparison.created_at.desc())
            .first()
        )
        if comp:
            comparison_data = {
                "id": str(comp.id),
                "status": comp.status,
                "scores": comp.scores,
                "recommended_vendor_id": (
                    str(comp.recommended_vendor_id) if comp.recommended_vendor_id else None
                ),
                "chosen_vendor_id": str(comp.chosen_vendor_id) if comp.chosen_vendor_id else None,
                "override_reason": comp.override_reason,
                "explanation": comp.explanation,
            }

    elif step.subject_type == "po":
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == step.subject_id).first()
        if not po:
            raise ProblemException(
                status_code=404,
                code="NOT_FOUND",
                title="Not Found",
                detail="Associated purchase order not found",
            )
        subject_data = {
            "id": str(po.id),
            "number": po.number,
            "status": po.status,
            "vendor_id": str(po.vendor_id),
            "department_id": str(po.department_id),
            "subtotal": str(po.subtotal),
            "vat": str(po.vat),
            "total": str(po.total),
            "currency": po.currency,
            "odoo_ref": po.odoo_ref,
            "lines": [
                {
                    "id": str(line.id),
                    "line_no": line.line_no,
                    "description": line.description,
                    "qty": str(line.qty),
                    "uom": line.uom,
                    "unit_price": str(line.unit_price),
                    "line_total": str(line.qty * line.unit_price),
                }
                for line in po.lines
            ],
        }

        # Check for match
        m = db.query(Match).filter(Match.po_id == po.id).order_by(Match.created_at.desc()).first()
        if m:
            match_data = {
                "id": str(m.id),
                "overall_status": m.overall_status,
                "tolerance_snapshot": m.tolerance_snapshot,
                "exceptions_count": len(m.exceptions),
            }

    return ApprovalBundleResponse(
        step_id=step.id,
        subject_type=step.subject_type,
        subject_id=step.subject_id,
        sequence=step.sequence,
        tier=step.tier,
        step_status=step.status,
        assigned_to=step.assigned_to,
        subject=subject_data,
        earlier_decisions=earlier_decisions,
        comparison=comparison_data,
        match=match_data,
    )


def record_decision(
    db: Session,
    step_id: uuid.UUID,
    decision: str,
    comment: str | None,
    principal: Principal,
) -> dict[str, Any]:
    step = db.query(ApprovalStep).filter(ApprovalStep.id == step_id).first()
    if not step:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail=f"Approval step '{step_id}' not found",
        )

    if step.status != "pending":
        raise ProblemException(
            status_code=409,
            code="STEP_NOT_PENDING",
            title="Conflict",
            detail=f"Approval step is already {step.status}",
        )

    # Check sequencing: earlier steps must be approved
    if step.sequence > 1:
        earlier_pending = (
            db.query(ApprovalStep)
            .filter(
                ApprovalStep.subject_type == step.subject_type,
                ApprovalStep.subject_id == step.subject_id,
                ApprovalStep.sequence < step.sequence,
                ApprovalStep.status != "approved",
            )
            .first()
        )
        if earlier_pending:
            raise ProblemException(
                status_code=409,
                code="EARLIER_STEP_PENDING",
                title="Conflict",
                detail="Previous approval step has not been approved",
            )

    # Fetch subject and verify creator SOD
    subject_total: Decimal = Decimal("0.00")
    pr: PurchaseRequest | None = None
    po: PurchaseOrder | None = None

    if step.subject_type == "pr":
        pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == step.subject_id).first()
        if not pr:
            raise ProblemException(
                status_code=404, code="NOT_FOUND", title="Not Found", detail="PR not found"
            )
        if pr.requester_id == principal.id:
            raise ProblemException(
                status_code=403,
                code="SOD_BLOCKED",
                title="Segregation of Duties Violation",
                detail="Creator cannot approve own purchase request",
            )
        subject_total = pr.total_aed
    elif step.subject_type == "po":
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == step.subject_id).first()
        if not po:
            raise ProblemException(
                status_code=404, code="NOT_FOUND", title="Not Found", detail="PO not found"
            )
        if po.created_by == principal.id:
            raise ProblemException(
                status_code=403,
                code="SOD_BLOCKED",
                title="Segregation of Duties Violation",
                detail="Creator cannot approve own purchase order",
            )
        subject_total = po.total

    # Authorization & Limits check
    has_manager = "manager" in principal.roles
    has_buyer = "buyer" in principal.roles

    if not has_manager and not has_buyer:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Admin without business role or user without spending authority cannot approve",
        )

    if not has_manager and has_buyer:
        # Buyer can ONLY approve Tier 1 (<= 5000 AED)
        if step.tier > 1 or subject_total > Decimal("5000.00"):
            raise ProblemException(
                status_code=403,
                code="ABOVE_LIMIT",
                title="Approval Limit Exceeded",
                detail="Buyer can only approve tier 1 items up to AED 5,000",
            )

    if has_manager:
        if principal.approval_limit_aed < subject_total:
            raise ProblemException(
                status_code=403,
                code="ABOVE_LIMIT",
                title="Approval Limit Exceeded",
                detail=(
                    f"Approver's spending limit (AED {principal.approval_limit_aed}) "
                    f"is below document total (AED {subject_total})"
                ),
            )

    clean_decision = decision.strip().lower()
    if clean_decision not in ("approve", "reject"):
        raise ProblemException(
            status_code=422,
            code="INVALID_DECISION",
            title="Invalid Decision",
            detail="Decision must be 'approve' or 'reject'",
        )

    if clean_decision == "reject" and (not comment or not comment.strip()):
        raise ProblemException(
            status_code=422,
            code="COMMENT_REQUIRED",
            title="Comment Required",
            detail="A comment or reason is required when rejecting",
        )

    step.decided_by = principal.id
    step.decided_at = datetime.now(timezone.utc)
    step.comment = comment.strip() if comment else None

    subject_status = ""

    if clean_decision == "approve":
        step.status = "approved"
        # Check if there is another pending step
        next_step = (
            db.query(ApprovalStep)
            .filter(
                ApprovalStep.subject_type == step.subject_type,
                ApprovalStep.subject_id == step.subject_id,
                ApprovalStep.sequence > step.sequence,
                ApprovalStep.status == "pending",
            )
            .order_by(ApprovalStep.sequence)
            .first()
        )
        if next_step:
            subject_status = "submitted"
        else:
            subject_status = "approved"
            if pr:
                pr.status = "approved"
            if po:
                po.status = "approved"

        record_audit(
            session=db,
            actor=principal,
            action="approval.approved",
            entity_type=f"{step.subject_type}_approval_step",
            entity_id=step.id,
            before={"status": "pending"},
            after={"status": "approved", "comment": step.comment, "subject_status": subject_status},
            reason=step.comment or "Approved step",
        )

    elif clean_decision == "reject":
        step.status = "rejected"
        subject_status = "rejected"
        if pr:
            pr.status = "rejected"
        if po:
            po.status = "rejected"

        # Skip remaining pending steps
        remaining = (
            db.query(ApprovalStep)
            .filter(
                ApprovalStep.subject_type == step.subject_type,
                ApprovalStep.subject_id == step.subject_id,
                ApprovalStep.sequence > step.sequence,
                ApprovalStep.status == "pending",
            )
            .all()
        )
        for r in remaining:
            r.status = "skipped"

        record_audit(
            session=db,
            actor=principal,
            action="approval.rejected",
            entity_type=f"{step.subject_type}_approval_step",
            entity_id=step.id,
            before={"status": "pending"},
            after={"status": "rejected", "comment": step.comment, "subject_status": subject_status},
            reason=step.comment,
        )

    db.commit()

    return {
        "step_id": step.id,
        "status": step.status,
        "decided_by": step.decided_by,
        "decided_at": step.decided_at,
        "comment": step.comment,
        "subject_status": subject_status,
    }
