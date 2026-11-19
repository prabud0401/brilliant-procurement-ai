import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.approvals.routing import build_approval_steps
from app.audit.service import record as record_audit
from app.core.errors import ProblemException
from app.core.models import (
    ApprovalStep,
    Comparison,
    ComparisonPairing,
    ComparisonQuote,
    Document,
    ExtractedLine,
    Outbox,
    POLine,
    PurchaseOrder,
    PurchaseRequest,
    User,
)
from app.core.policy import Principal
from app.integrations import get_odoo_adapter
from app.orders.schemas import POCreateRequest, POPushResponse, POResponse


def _generate_po_number(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    suffix = uuid.uuid4().hex[:6].upper()
    return f"PO-{year}-{suffix}"


def _get_current_approver(db: Session, po_id: uuid.UUID) -> tuple[uuid.UUID | None, str | None]:
    step = (
        db.query(ApprovalStep)
        .filter(
            ApprovalStep.subject_type == "po",
            ApprovalStep.subject_id == po_id,
            ApprovalStep.status == "pending",
        )
        .order_by(ApprovalStep.sequence)
        .first()
    )
    if not step or not step.assigned_to:
        return None, None
    user = db.query(User).filter(User.id == step.assigned_to).first()
    return step.assigned_to, user.display_name if user else None


def create_po_from_comparison(
    db: Session,
    body: POCreateRequest,
    principal: Principal,
) -> POResponse:
    comp = db.query(Comparison).filter(Comparison.id == body.comparison_id).first()
    if not comp:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail=f"Comparison '{body.comparison_id}' not found",
        )

    if comp.status != "decided" or not comp.chosen_vendor_id:
        raise ProblemException(
            status_code=409,
            code="COMPARISON_NOT_DECIDED",
            title="Conflict",
            detail=(
                "A purchase order can only be created from a decided "
                "comparison with a chosen vendor"
            ),
        )

    pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == comp.pr_id).first()
    if not pr:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Associated purchase request not found",
        )

    # Find the document for the chosen vendor in this comparison
    chosen_doc = (
        db.query(Document)
        .join(ComparisonQuote, Document.id == ComparisonQuote.document_id)
        .filter(
            ComparisonQuote.comparison_id == comp.id,
            Document.vendor_id == comp.chosen_vendor_id,
        )
        .first()
    )

    # Load paired extracted lines
    pairings: list[ComparisonPairing] = []
    if chosen_doc:
        pairings = (
            db.query(ComparisonPairing)
            .filter(
                ComparisonPairing.comparison_id == comp.id,
                ComparisonPairing.document_id == chosen_doc.id,
                ComparisonPairing.extracted_line_id.isnot(None),
            )
            .all()
        )

    po_lines_data: list[dict[str, Any]] = []
    line_no = 1
    subtotal = Decimal("0.00")

    for p in pairings:
        ext_line = db.query(ExtractedLine).filter(ExtractedLine.id == p.extracted_line_id).first()
        if ext_line:
            qty = ext_line.qty or Decimal("1.00")
            unit_price = ext_line.unit_price or Decimal("0.00")
            line_tot = qty * unit_price
            subtotal += line_tot
            po_lines_data.append(
                {
                    "line_no": line_no,
                    "product_id": None,
                    "description": ext_line.description or f"Item {line_no}",
                    "qty": qty,
                    "uom": ext_line.uom or "unit",
                    "unit_price": unit_price,
                    "vat_rate": Decimal("0.05"),
                }
            )
            line_no += 1

    # Fallback: if no pairings lines, copy from PR lines
    if not po_lines_data:
        for pr_line in pr.lines:
            line_tot = pr_line.qty * pr_line.est_unit_price
            subtotal += line_tot
            po_lines_data.append(
                {
                    "line_no": line_no,
                    "product_id": pr_line.product_id,
                    "description": pr_line.description,
                    "qty": pr_line.qty,
                    "uom": pr_line.uom,
                    "unit_price": pr_line.est_unit_price,
                    "vat_rate": Decimal("0.05"),
                }
            )
            line_no += 1

    vat = (subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
    total = subtotal + vat
    po_number = _generate_po_number(db)

    po = PurchaseOrder(
        number=po_number,
        comparison_id=comp.id,
        vendor_id=comp.chosen_vendor_id,
        created_by=principal.id,
        department_id=pr.department_id,
        status="draft",
        subtotal=subtotal,
        vat=vat,
        total=total,
        currency="AED",
    )
    db.add(po)
    db.flush()

    for pld in po_lines_data:
        po_line = POLine(
            po_id=po.id,
            line_no=pld["line_no"],
            product_id=pld["product_id"],
            description=pld["description"],
            qty=pld["qty"],
            uom=pld["uom"],
            unit_price=pld["unit_price"],
            vat_rate=pld["vat_rate"],
            created_by=principal.id,
        )
        db.add(po_line)

    db.flush()

    record_audit(
        session=db,
        actor=principal,
        action="po.created",
        entity_type="purchase_order",
        entity_id=po.id,
        after={
            "number": po.number,
            "comparison_id": str(comp.id),
            "vendor_id": str(po.vendor_id),
            "total": str(po.total),
            "lines_count": len(po_lines_data),
        },
        reason="Purchase order created from comparison in draft",
    )
    db.commit()

    return POResponse.model_validate(po)


def list_pos(
    db: Session,
    principal: Principal,
    status_filter: str | None = None,
) -> list[POResponse]:
    query = db.query(PurchaseOrder)

    if "buyer" in principal.roles or "admin" in principal.roles:
        pass
    elif "manager" in principal.roles:
        if principal.department_id:
            query = query.filter(PurchaseOrder.department_id == principal.department_id)
        else:
            query = query.filter(PurchaseOrder.created_by == principal.id)
    else:
        # Requester sees POs for their own PRs
        query = (
            query.join(Comparison, PurchaseOrder.comparison_id == Comparison.id)
            .join(PurchaseRequest, Comparison.pr_id == PurchaseRequest.id)
            .filter(PurchaseRequest.requester_id == principal.id)
        )

    if status_filter:
        query = query.filter(PurchaseOrder.status == status_filter.strip().lower())

    pos = query.order_by(PurchaseOrder.created_at.desc()).all()
    results: list[POResponse] = []
    for po in pos:
        approver_id, approver_name = _get_current_approver(db, po.id)
        resp = POResponse.model_validate(po)
        resp.current_approver_id = approver_id
        resp.current_approver = approver_name
        results.append(resp)
    return results


def get_po(db: Session, po_id: uuid.UUID, principal: Principal) -> POResponse:
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail=f"Purchase order '{po_id}' not found",
        )

    # Scoped check
    if "buyer" not in principal.roles and "admin" not in principal.roles:
        if "manager" in principal.roles:
            if po.department_id != principal.department_id:
                raise ProblemException(
                    status_code=404,
                    code="NOT_FOUND",
                    title="Not Found",
                    detail="Purchase order not found in department scope",
                )
        else:
            # Requester
            pr = (
                db.query(PurchaseRequest)
                .join(Comparison, Comparison.pr_id == PurchaseRequest.id)
                .filter(Comparison.id == po.comparison_id)
                .first()
            )
            if not pr or pr.requester_id != principal.id:
                raise ProblemException(
                    status_code=404,
                    code="NOT_FOUND",
                    title="Not Found",
                    detail="Purchase order not found in owner scope",
                )

    approver_id, approver_name = _get_current_approver(db, po.id)
    resp = POResponse.model_validate(po)
    resp.current_approver_id = approver_id
    resp.current_approver = approver_name
    return resp


def submit_po(db: Session, po_id: uuid.UUID, principal: Principal) -> POResponse:
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="PO not found",
        )

    if po.created_by != principal.id and "buyer" not in principal.roles:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Only the creator or a Buyer can submit this purchase order",
        )

    if po.status != "draft":
        raise ProblemException(
            status_code=409,
            code="PO_NOT_DRAFT",
            title="Conflict",
            detail=f"Cannot submit purchase order in status '{po.status}'",
        )

    steps, rule_snapshot = build_approval_steps(
        db=db,
        subject_type="po",
        subject_id=po.id,
        total_aed=po.total,
        department_id=po.department_id,
        creator_id=po.created_by,
    )

    po.status = "submitted"
    po.rule_snapshot = rule_snapshot
    po.updated_at = datetime.now(timezone.utc)
    db.flush()

    record_audit(
        session=db,
        actor=principal,
        action="po.submitted",
        entity_type="purchase_order",
        entity_id=po.id,
        before={"status": "draft"},
        after={"status": "submitted", "tier": rule_snapshot.get("tier"), "steps": len(steps)},
        reason="Purchase order submitted for approval",
    )
    db.commit()

    approver_id, approver_name = _get_current_approver(db, po.id)
    resp = POResponse.model_validate(po)
    resp.current_approver_id = approver_id
    resp.current_approver = approver_name
    return resp


def push_po_to_odoo(
    db: Session,
    po_id: uuid.UUID,
    idempotency_key: str,
    principal: Principal,
) -> POPushResponse:
    if not idempotency_key or not idempotency_key.strip():
        raise ProblemException(
            status_code=422,
            code="IDEMPOTENCY_KEY_REQUIRED",
            title="Unprocessable Entity",
            detail="Header 'Idempotency-Key' is required to push PO to Odoo",
        )

    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="PO not found",
        )

    # Idempotent re-execution
    if po.idempotency_key == idempotency_key.strip() and po.status == "sent_to_vendor":
        return POPushResponse(status=po.status, odoo_ref=po.odoo_ref or "")

    if po.status not in ("approved", "sent_to_vendor"):
        raise ProblemException(
            status_code=409,
            code="PO_NOT_APPROVED",
            title="Conflict",
            detail=f"Cannot push purchase order in status '{po.status}' to Odoo (must be approved)",
        )

    # Format PO data for Odoo adapter
    po_data: dict[str, Any] = {
        "po_number": po.number,
        "vendor_odoo_id": 1,
        "vendor_name": "Vendor",
        "status": "confirmed",
        "subtotal": po.subtotal,
        "vat": po.vat,
        "total": po.total,
        "currency": po.currency,
        "lines": [
            {
                "line_no": line.line_no,
                "product_code": "",
                "description": line.description,
                "qty": line.qty,
                "uom": line.uom,
                "unit_price": line.unit_price,
                "vat_rate": Decimal("5.00"),
                "line_total": line.qty * line.unit_price,
            }
            for line in po.lines
        ],
    }

    adapter = get_odoo_adapter()
    odoo_po = adapter.create_or_confirm_po(po_data, idempotency_key=idempotency_key.strip())

    # Create Outbox record
    outbox = Outbox(
        event_type="po.pushed_to_odoo",
        payload={
            "po_id": str(po.id),
            "po_number": po.number,
            "odoo_ref": odoo_po.odoo_ref,
            "total": str(po.total),
        },
        idempotency_key=idempotency_key.strip(),
        status="completed",
    )
    db.add(outbox)

    old_status = po.status
    po.status = "sent_to_vendor"
    po.odoo_ref = odoo_po.odoo_ref
    po.idempotency_key = idempotency_key.strip()
    po.updated_at = datetime.now(timezone.utc)
    db.flush()

    record_audit(
        session=db,
        actor=principal,
        action="po.pushed_to_odoo",
        entity_type="purchase_order",
        entity_id=po.id,
        before={"status": old_status},
        after={"status": po.status, "odoo_ref": po.odoo_ref},
        reason=f"PO pushed to Odoo with reference {odoo_po.odoo_ref}",
    )
    db.commit()

    return POPushResponse(status=po.status, odoo_ref=po.odoo_ref or "")
