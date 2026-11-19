import difflib
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.audit.service import record as record_audit
from app.core.errors import ProblemException
from app.core.models import (
    Document,
    ExtractedField,
    Extraction,
    Match,
    MatchException,
    MatchLine,
    POLine,
    PurchaseOrder,
    User,
    UserRole,
)
from app.core.policy import Principal
from app.matching.engine import execute_three_way_match
from app.matching.schemas import (
    ExceptionResolveRequest,
    MatchExceptionResponse,
    MatchResponse,
)
from app.settings_api.service import get_setting


def _get_doc_field(db: Session, doc_id: uuid.UUID, field_name: str) -> str | None:
    extraction = (
        db.query(Extraction)
        .filter(Extraction.document_id == doc_id)
        .order_by(Extraction.version.desc())
        .first()
    )
    if not extraction:
        return None
    field = (
        db.query(ExtractedField)
        .filter(ExtractedField.extraction_id == extraction.id, ExtractedField.name == field_name)
        .first()
    )
    if not field:
        return None
    return field.value_raw


def create_match(
    db: Session,
    invoice_document_id: uuid.UUID,
    principal: Principal,
) -> MatchResponse:
    invoice_doc = db.query(Document).filter(Document.id == invoice_document_id).first()
    if not invoice_doc:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail=f"Invoice document '{invoice_document_id}' not found",
        )

    if invoice_doc.doc_type != "invoice":
        raise ProblemException(
            status_code=422,
            code="INVALID_DOC_TYPE",
            title="Unprocessable Entity",
            detail=f"Document '{invoice_document_id}' is not an invoice",
        )

    if invoice_doc.status != "confirmed":
        raise ProblemException(
            status_code=422,
            code="DOCUMENT_NOT_CONFIRMED",
            title="Unprocessable Entity",
            detail=f"Invoice document '{invoice_document_id}' is not confirmed yet",
        )

    # Find PO
    po: PurchaseOrder | None = None
    if invoice_doc.po_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == invoice_doc.po_id).first()

    if not po:
        po_number_raw = _get_doc_field(db, invoice_doc.id, "po_number") or _get_doc_field(
            db, invoice_doc.id, "buyer_reference"
        )
        if po_number_raw:
            po = (
                db.query(PurchaseOrder)
                .filter(PurchaseOrder.number == po_number_raw.strip())
                .first()
            )

    if not po:
        raise ProblemException(
            status_code=422,
            code="PO_NOT_FOUND",
            title="Unprocessable Entity",
            detail="Matching purchase order not found for this invoice",
        )

    # Fetch delivery notes confirmed for this PO
    dn_docs = (
        db.query(Document)
        .filter(
            Document.po_id == po.id,
            Document.doc_type == "delivery_note",
            Document.status == "confirmed",
        )
        .all()
    )

    # Accumulate received quantities by PO line
    dn_lines_by_po_line: dict[uuid.UUID, list[Decimal]] = {pl.id: [] for pl in po.lines}

    for dn_doc in dn_docs:
        dn_ext = (
            db.query(Extraction)
            .filter(Extraction.document_id == dn_doc.id)
            .order_by(Extraction.version.desc())
            .first()
        )
        if dn_ext:
            for dn_line in dn_ext.lines:
                qty = dn_line.qty or Decimal("0.00")
                # Match DN line to PO line
                matched_pl: POLine | None = None
                if dn_line.item_code:
                    for pl in po.lines:
                        if dn_line.item_code.lower() in pl.description.lower():
                            matched_pl = pl
                            break
                if not matched_pl and dn_line.description:
                    for pl in po.lines:
                        score = difflib.SequenceMatcher(
                            None, dn_line.description.lower(), pl.description.lower()
                        ).ratio()
                        if score >= 0.40:
                            matched_pl = pl
                            break
                if not matched_pl and po.lines:
                    matched_pl = po.lines[0]

                if matched_pl:
                    dn_lines_by_po_line[matched_pl.id].append(qty)

    # Invoice lines
    inv_ext = (
        db.query(Extraction)
        .filter(Extraction.document_id == invoice_doc.id)
        .order_by(Extraction.version.desc())
        .first()
    )
    invoice_lines = inv_ext.lines if inv_ext else []

    # Tolerances snapshot
    tolerances_setting = get_setting(db, "tolerances")
    tolerances = tolerances_setting.get("value", {})

    vat_raw = _get_doc_field(db, invoice_doc.id, "vat_amount")
    invoice_vat = Decimal(str(vat_raw)) if vat_raw else Decimal("0.00")

    result = execute_three_way_match(
        po_lines=po.lines,
        invoice_lines=invoice_lines,
        dn_lines_by_po_line=dn_lines_by_po_line,
        invoice_vat=invoice_vat,
        tolerances=tolerances,
    )

    # Create match record
    match = Match(
        invoice_document_id=invoice_doc.id,
        po_id=po.id,
        run_by=principal.id,
        tolerance_snapshot=tolerances,
        overall_status=result["overall_status"],
        created_by=principal.id,
    )
    db.add(match)
    db.flush()

    # Save match lines
    saved_lines: list[MatchLine] = []
    line_map_by_invoice_id: dict[uuid.UUID, uuid.UUID] = {}

    for l_data in result["lines"]:
        ml = MatchLine(
            match_id=match.id,
            po_line_id=l_data["po_line_id"],
            invoice_line_id=l_data["invoice_line_id"],
            ordered_qty=l_data["ordered_qty"],
            received_qty=l_data["received_qty"],
            invoiced_qty=l_data["invoiced_qty"],
            po_unit_price=l_data["po_unit_price"],
            inv_unit_price=l_data["inv_unit_price"],
            variance_aed=l_data["variance_aed"],
            status=l_data["status"],
            reason=l_data["reason"],
            created_by=principal.id,
        )
        db.add(ml)
        db.flush()
        saved_lines.append(ml)
        if ml.invoice_line_id:
            line_map_by_invoice_id[ml.invoice_line_id] = ml.id

    # Save exceptions
    for exc in result["exceptions"]:
        inv_id = exc.get("invoice_line_id")
        ml_id = line_map_by_invoice_id.get(inv_id) if inv_id else None

        me = MatchException(
            match_id=match.id,
            match_line_id=ml_id,
            kind=exc["kind"],
            reason=exc["reason"],
            amount_impact_aed=exc["amount_impact_aed"],
            status="open",
            created_by=principal.id,
        )
        db.add(me)

    db.flush()

    record_audit(
        session=db,
        actor=principal,
        action="match.created",
        entity_type="match",
        entity_id=match.id,
        after={
            "invoice_document_id": str(invoice_doc.id),
            "po_id": str(po.id),
            "overall_status": match.overall_status,
            "exceptions_count": len(result["exceptions"]),
        },
        reason="Three-way match executed",
    )
    db.commit()

    return get_match(db, match.id, principal)


def get_match(db: Session, match_id: uuid.UUID, principal: Principal) -> MatchResponse:
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail=f"Match '{match_id}' not found",
        )

    return MatchResponse.model_validate(match)


def list_exceptions(
    db: Session,
    principal: Principal,
    status_filter: str | None = None,
) -> list[MatchExceptionResponse]:
    query = db.query(MatchException)

    if "buyer" in principal.roles or "admin" in principal.roles:
        pass
    elif "manager" in principal.roles:
        # Manager sees escalated exceptions or assigned to them or their department
        query = query.filter(
            (MatchException.status == "escalated") | (MatchException.assigned_to == principal.id)
        )
    else:
        return []

    if status_filter:
        query = query.filter(MatchException.status == status_filter.strip().lower())

    exceptions = query.order_by(MatchException.created_at.desc()).all()
    return [MatchExceptionResponse.model_validate(e) for e in exceptions]


def resolve_exception(
    db: Session,
    exception_id: uuid.UUID,
    body: ExceptionResolveRequest,
    principal: Principal,
) -> MatchExceptionResponse:
    exc = db.query(MatchException).filter(MatchException.id == exception_id).first()
    if not exc:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail=f"Match exception '{exception_id}' not found",
        )

    if exc.status in ("accepted", "rejected"):
        raise ProblemException(
            status_code=409,
            code="EXCEPTION_ALREADY_RESOLVED",
            title="Conflict",
            detail=f"Exception has already been {exc.status}",
        )

    act = body.action.strip().lower()
    reason = body.reason.strip()

    is_manager = "manager" in principal.roles
    is_buyer = "buyer" in principal.roles

    if not is_manager and not is_buyer:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Business role required to resolve exceptions",
        )

    if exc.status == "escalated" and not is_manager:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Only a Manager can decide an escalated exception",
        )

    if act == "accept":
        # Check Buyer restrictions
        if not is_manager and is_buyer:
            # 1. Never accept over-billing
            if exc.kind == "qty_variance":
                raise ProblemException(
                    status_code=403,
                    code="BUYER_OVERBILLING_BLOCKED",
                    title="Policy Violation",
                    detail=(
                        "Buyer cannot accept quantity over-billing exceptions; "
                        "must escalate to Manager"
                    ),
                )

            # 2. Check policy limit (default 500 AED)
            policy = get_setting(db, "buyer-policy").get("value", {})
            max_policy = Decimal(str(policy.get("max_amount_aed", "500.00")))
            if exc.amount_impact_aed > max_policy:
                raise ProblemException(
                    status_code=403,
                    code="BUYER_POLICY_LIMIT_EXCEEDED",
                    title="Policy Violation",
                    detail=(
                        f"Amount impact AED {exc.amount_impact_aed} exceeds "
                        f"Buyer exception policy limit of AED {max_policy}; must escalate"
                    ),
                )

        exc.status = "accepted"
        exc.resolution = "accepted"
        exc.resolution_reason = reason
        exc.resolved_by = principal.id

    elif act == "escalate":
        exc.status = "escalated"
        exc.resolution_reason = reason
        # Assign to Manager
        match = db.query(Match).filter(Match.id == exc.match_id).first()
        po = (
            db.query(PurchaseOrder).filter(PurchaseOrder.id == match.po_id).first()
            if match
            else None
        )
        if po:
            mgr = (
                db.query(User)
                .join(UserRole, User.id == UserRole.user_id)
                .filter(
                    UserRole.role == "manager",
                    User.department_id == po.department_id,
                    User.active.is_(True),
                )
                .first()
            )
            if mgr:
                exc.assigned_to = mgr.id

    elif act in ("reject", "reject_credit_note"):
        exc.status = "rejected"
        exc.resolution = "credit_note_requested"
        exc.resolution_reason = reason
        exc.resolved_by = principal.id

    elif act == "wait":
        exc.status = "waiting"
        exc.resolution_reason = reason

    else:
        raise ProblemException(
            status_code=422,
            code="INVALID_ACTION",
            title="Unprocessable Entity",
            detail=f"Unknown exception resolution action: '{body.action}'",
        )

    exc.updated_at = datetime.now(timezone.utc)
    db.flush()

    # If all exceptions accepted, update match overall_status
    all_exceptions = db.query(MatchException).filter(MatchException.match_id == exc.match_id).all()
    if all(e.status == "accepted" for e in all_exceptions):
        match = db.query(Match).filter(Match.id == exc.match_id).first()
        if match:
            match.overall_status = "within_tolerance"
            match.updated_at = datetime.now(timezone.utc)

    record_audit(
        session=db,
        actor=principal,
        action="match.exception_resolved",
        entity_type="match_exception",
        entity_id=exc.id,
        after={
            "action": act,
            "status": exc.status,
            "reason": exc.resolution_reason,
            "resolved_by": str(principal.id),
        },
        reason=f"Exception resolved with action '{act}'",
    )
    db.commit()

    return MatchExceptionResponse.model_validate(exc)
