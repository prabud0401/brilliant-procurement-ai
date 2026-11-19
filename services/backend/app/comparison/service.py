import difflib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.audit.service import record as record_audit
from app.comparison.explanation import ExplanationWriter, generate_explained_recommendation
from app.comparison.schemas import (
    ComparisonCreateRequest,
    ComparisonQuoteResponse,
    ComparisonResponse,
    DecisionRequest,
    PairingResponse,
    PairingUpdateItem,
    QuoteUpdateItem,
    RecommendationResponse,
    WeightsUpdateRequest,
)
from app.comparison.scoring import calculate_scores
from app.core.errors import ProblemException
from app.core.models import (
    Comparison,
    ComparisonPairing,
    ComparisonQuote,
    Document,
    ExtractedField,
    ExtractedLine,
    Extraction,
    PurchaseRequest,
    Vendor,
)
from app.core.policy import Principal


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


def create_comparison(
    db: Session,
    body: ComparisonCreateRequest,
    principal: Principal,
) -> ComparisonResponse:
    if len(body.quote_document_ids) < 2:
        raise ProblemException(
            status_code=422,
            code="INSUFFICIENT_QUOTES",
            title="Unprocessable Entity",
            detail="At least two confirmed quotes are required to create a comparison",
        )

    pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == body.pr_id).first()
    if not pr:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail=f"Purchase request '{body.pr_id}' not found",
        )

    # Validate quotes
    docs: list[Document] = []
    for doc_id in body.quote_document_ids:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise ProblemException(
                status_code=404,
                code="NOT_FOUND",
                title="Not Found",
                detail=f"Document '{doc_id}' not found",
            )
        if doc.doc_type != "quote":
            raise ProblemException(
                status_code=422,
                code="INVALID_DOC_TYPE",
                title="Unprocessable Entity",
                detail=f"Document '{doc_id}' is not a quotation",
            )
        if doc.status != "confirmed":
            raise ProblemException(
                status_code=422,
                code="DOCUMENT_NOT_CONFIRMED",
                title="Unprocessable Entity",
                detail=f"Quotation '{doc_id}' is not confirmed yet",
            )
        docs.append(doc)

    comparison = Comparison(
        pr_id=pr.id,
        created_by=principal.id,
        status="draft",
        weights={"cost": 60, "delivery": 20, "payment": 10, "completeness": 10},
    )
    db.add(comparison)
    db.flush()

    today = datetime.now(timezone.utc).date()
    flags: list[str] = []

    # Process quote documents
    for doc in docs:
        is_expired = False
        validity_val = _get_doc_field(db, doc.id, "validity_date")
        if validity_val:
            try:
                val_date = datetime.fromisoformat(validity_val).date()
                if val_date < today:
                    is_expired = True
                    flags.append(f"Document {doc.id} is expired")
            except Exception:
                pass

        currency_val = _get_doc_field(db, doc.id, "currency") or "AED"
        if currency_val.upper() != pr.currency.upper():
            flags.append(f"Document {doc.id} currency mismatch: {currency_val} vs {pr.currency}")

        trn_val = _get_doc_field(db, doc.id, "vendor_trn") or _get_doc_field(db, doc.id, "trn")
        if not trn_val or len(trn_val.strip()) != 15:
            flags.append(f"Document {doc.id} has missing or invalid TRN")

        quote_row = ComparisonQuote(
            comparison_id=comparison.id,
            document_id=doc.id,
            included=not is_expired,
            include_reason="Included on creation" if not is_expired else None,
            created_by=principal.id,
        )
        db.add(quote_row)

        # Pair lines for this document
        extraction = (
            db.query(Extraction)
            .filter(Extraction.document_id == doc.id)
            .order_by(Extraction.version.desc())
            .first()
        )
        ext_lines: list[ExtractedLine] = extraction.lines if extraction else []

        for pr_line in pr.lines:
            matched_line: ExtractedLine | None = None
            method = "similarity"

            # 1. Exact match by item code
            for el in ext_lines:
                if el.item_code and pr_line.description:
                    if (
                        el.item_code.lower() in pr_line.description.lower()
                        or pr_line.description.lower() in el.item_code.lower()
                    ):
                        matched_line = el
                        method = "code"
                        break

            # 2. Text similarity
            if not matched_line and ext_lines:
                best_ratio = 0.0
                best_el: ExtractedLine | None = None
                for el in ext_lines:
                    desc = el.description or ""
                    ratio = difflib.SequenceMatcher(
                        None, pr_line.description.lower(), desc.lower()
                    ).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_el = el
                if best_ratio >= 0.40 and best_el:
                    matched_line = best_el
                    method = "similarity"

            pairing = ComparisonPairing(
                comparison_id=comparison.id,
                pr_line_id=pr_line.id,
                document_id=doc.id,
                extracted_line_id=matched_line.id if matched_line else None,
                method=method,
                created_by=principal.id,
            )
            db.add(pairing)

    db.flush()

    record_audit(
        session=db,
        actor=principal,
        action="comparison.created",
        entity_type="comparison",
        entity_id=comparison.id,
        after={
            "pr_id": str(pr.id),
            "quotes_count": len(docs),
            "weights": comparison.weights,
        },
        reason="Quote comparison created in draft",
    )
    db.commit()

    return get_comparison(db, comparison.id, principal)


def get_comparison(
    db: Session,
    comparison_id: uuid.UUID,
    principal: Principal,
) -> ComparisonResponse:
    comparison = db.query(Comparison).filter(Comparison.id == comparison_id).first()
    if not comparison:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail=f"Comparison '{comparison_id}' not found",
        )

    pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == comparison.pr_id).first()
    if not pr:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Associated PR not found",
        )

    # Scoped check
    if "buyer" not in principal.roles and "admin" not in principal.roles:
        if "manager" in principal.roles:
            if pr.department_id != principal.department_id:
                raise ProblemException(
                    status_code=404,
                    code="NOT_FOUND",
                    title="Not Found",
                    detail="Comparison not in department scope",
                )
        else:
            if pr.requester_id != principal.id:
                raise ProblemException(
                    status_code=404,
                    code="NOT_FOUND",
                    title="Not Found",
                    detail="Comparison not in owner scope",
                )

    quotes_data: list[ComparisonQuoteResponse] = []
    comp_quotes = (
        db.query(ComparisonQuote).filter(ComparisonQuote.comparison_id == comparison.id).all()
    )
    flags: list[str] = []
    today = datetime.now(timezone.utc).date()

    for cq in comp_quotes:
        doc = db.query(Document).filter(Document.id == cq.document_id).first()
        vendor = db.query(Vendor).filter(Vendor.id == doc.vendor_id).first() if doc else None

        validity_val = _get_doc_field(db, cq.document_id, "validity_date")
        is_expired = False
        if validity_val:
            try:
                val_date = datetime.fromisoformat(validity_val).date()
                if val_date < today:
                    is_expired = True
                    flags.append(f"Quote {cq.document_id} is expired")
            except Exception:
                pass

        total_val = _get_doc_field(db, cq.document_id, "total")
        total_aed = Decimal(str(total_val)) if total_val else Decimal("0.00")
        lead_val = _get_doc_field(db, cq.document_id, "lead_time_days")
        lead_time = int(lead_val) if lead_val and lead_val.isdigit() else None
        pay_val = _get_doc_field(db, cq.document_id, "payment_terms_days")
        pay_terms = (
            int(pay_val)
            if pay_val and pay_val.isdigit()
            else (vendor.payment_terms_days if vendor else 30)
        )

        quotes_data.append(
            ComparisonQuoteResponse(
                document_id=cq.document_id,
                vendor_id=doc.vendor_id if doc else None,
                vendor_name=vendor.name if vendor else (doc.source if doc else "Vendor"),
                included=cq.included,
                include_reason=cq.include_reason,
                is_expired=is_expired,
                currency=_get_doc_field(db, cq.document_id, "currency") or "AED",
                total_aed=total_aed,
                lead_time_days=lead_time,
                payment_terms_days=pay_terms,
            )
        )

    pairings = (
        db.query(ComparisonPairing).filter(ComparisonPairing.comparison_id == comparison.id).all()
    )
    pairings_data = [PairingResponse.model_validate(p) for p in pairings]

    return ComparisonResponse(
        id=comparison.id,
        pr_id=comparison.pr_id,
        created_by=comparison.created_by,
        status=comparison.status,
        weights=comparison.weights,
        scores=comparison.scores,
        recommended_vendor_id=comparison.recommended_vendor_id,
        chosen_vendor_id=comparison.chosen_vendor_id,
        override_reason=comparison.override_reason,
        explanation=comparison.explanation,
        created_at=comparison.created_at,
        quotes=quotes_data,
        pairings=pairings_data,
        flags=flags,
    )


def update_pairings(
    db: Session,
    comparison_id: uuid.UUID,
    pairings: list[PairingUpdateItem],
    principal: Principal,
) -> ComparisonResponse:
    comparison = db.query(Comparison).filter(Comparison.id == comparison_id).first()
    if not comparison:
        raise ProblemException(
            status_code=404, code="NOT_FOUND", title="Not Found", detail="Comparison not found"
        )

    for item in pairings:
        pairing = (
            db.query(ComparisonPairing)
            .filter(
                ComparisonPairing.comparison_id == comparison.id,
                ComparisonPairing.pr_line_id == item.pr_line_id,
                ComparisonPairing.document_id == item.document_id,
            )
            .first()
        )
        if pairing:
            pairing.extracted_line_id = item.extracted_line_id
            pairing.method = "manual"
            pairing.updated_at = datetime.now(timezone.utc)
        else:
            new_pairing = ComparisonPairing(
                comparison_id=comparison.id,
                pr_line_id=item.pr_line_id,
                document_id=item.document_id,
                extracted_line_id=item.extracted_line_id,
                method="manual",
                created_by=principal.id,
            )
            db.add(new_pairing)

    db.flush()

    record_audit(
        session=db,
        actor=principal,
        action="comparison.pairings_updated",
        entity_type="comparison",
        entity_id=comparison.id,
        after={"updated_count": len(pairings)},
        reason="Manual update of comparison pairings",
    )
    db.commit()

    return get_comparison(db, comparison.id, principal)


def update_quote(
    db: Session,
    comparison_id: uuid.UUID,
    document_id: uuid.UUID,
    item: QuoteUpdateItem,
    principal: Principal,
) -> ComparisonResponse:
    cq = (
        db.query(ComparisonQuote)
        .filter(
            ComparisonQuote.comparison_id == comparison_id,
            ComparisonQuote.document_id == document_id,
        )
        .first()
    )
    if not cq:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Quote not found in comparison",
        )

    validity_val = _get_doc_field(db, document_id, "validity_date")
    today = datetime.now(timezone.utc).date()
    is_expired = False
    if validity_val:
        try:
            if datetime.fromisoformat(validity_val).date() < today:
                is_expired = True
        except Exception:
            pass

    if (
        is_expired
        and item.included
        and (not item.include_reason or not item.include_reason.strip())
    ):
        raise ProblemException(
            status_code=422,
            code="INCLUDE_REASON_REQUIRED",
            title="Unprocessable Entity",
            detail="A reason is required to include an expired quotation",
        )

    cq.included = item.included
    cq.include_reason = item.include_reason.strip() if item.include_reason else None
    cq.updated_at = datetime.now(timezone.utc)
    db.flush()

    record_audit(
        session=db,
        actor=principal,
        action="comparison.quote_updated",
        entity_type="comparison_quote",
        entity_id=cq.id,
        after={
            "document_id": str(document_id),
            "included": cq.included,
            "reason": cq.include_reason,
        },
        reason="Updated quote inclusion status",
    )
    db.commit()

    return get_comparison(db, comparison_id, principal)


def update_weights(
    db: Session,
    comparison_id: uuid.UUID,
    weights: WeightsUpdateRequest,
    principal: Principal,
) -> ComparisonResponse:
    if weights.cost + weights.delivery + weights.payment + weights.completeness != 100:
        raise ProblemException(
            status_code=422,
            code="INVALID_WEIGHTS",
            title="Unprocessable Entity",
            detail="Weights must sum to 100",
        )

    comparison = db.query(Comparison).filter(Comparison.id == comparison_id).first()
    if not comparison:
        raise ProblemException(
            status_code=404, code="NOT_FOUND", title="Not Found", detail="Comparison not found"
        )

    old_weights = comparison.weights
    new_weights = {
        "cost": weights.cost,
        "delivery": weights.delivery,
        "payment": weights.payment,
        "completeness": weights.completeness,
    }
    comparison.weights = new_weights
    comparison.updated_at = datetime.now(timezone.utc)
    db.flush()

    # If already recommended, recalculate scores
    if comparison.scores:
        compute_recommendation(db, comparison.id, principal)

    record_audit(
        session=db,
        actor=principal,
        action="comparison.weights_updated",
        entity_type="comparison",
        entity_id=comparison.id,
        before={"weights": old_weights},
        after={"weights": new_weights},
        reason="Updated comparison criterion weights",
    )
    db.commit()

    return get_comparison(db, comparison.id, principal)


def compute_recommendation(
    db: Session,
    comparison_id: uuid.UUID,
    principal: Principal,
    writer: ExplanationWriter | None = None,
) -> RecommendationResponse:
    comparison = db.query(Comparison).filter(Comparison.id == comparison_id).first()
    if not comparison:
        raise ProblemException(
            status_code=404, code="NOT_FOUND", title="Not Found", detail="Comparison not found"
        )

    pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == comparison.pr_id).first()
    if not pr:
        raise ProblemException(
            status_code=404, code="NOT_FOUND", title="Not Found", detail="PR not found"
        )

    total_items = len(pr.lines)
    comp_quotes = (
        db.query(ComparisonQuote)
        .filter(
            ComparisonQuote.comparison_id == comparison.id,
            ComparisonQuote.included.is_(True),
        )
        .all()
    )

    if not comp_quotes:
        raise ProblemException(
            status_code=422,
            code="NO_INCLUDED_QUOTES",
            title="Unprocessable Entity",
            detail="No included quotes available to generate recommendation",
        )

    quotes_data: list[dict[str, Any]] = []

    for cq in comp_quotes:
        doc = db.query(Document).filter(Document.id == cq.document_id).first()
        if not doc or not doc.vendor_id:
            continue
        vendor = db.query(Vendor).filter(Vendor.id == doc.vendor_id).first()
        vendor_name = vendor.name if vendor else "Vendor"

        # Count paired items
        paired_count = (
            db.query(ComparisonPairing)
            .filter(
                ComparisonPairing.comparison_id == comparison.id,
                ComparisonPairing.document_id == cq.document_id,
                ComparisonPairing.extracted_line_id.isnot(None),
            )
            .count()
        )

        total_val = _get_doc_field(db, cq.document_id, "total")
        total_cost = Decimal(str(total_val)) if total_val else Decimal("0.00")

        lead_val = _get_doc_field(db, cq.document_id, "lead_time_days")
        lead_time = int(lead_val) if lead_val and lead_val.isdigit() else 7

        pay_val = _get_doc_field(db, cq.document_id, "payment_terms_days")
        pay_terms = (
            int(pay_val)
            if pay_val and pay_val.isdigit()
            else (vendor.payment_terms_days if vendor else 30)
        )

        quotes_data.append(
            {
                "vendor_id": doc.vendor_id,
                "vendor_name": vendor_name,
                "total_cost": total_cost,
                "lead_time_days": lead_time,
                "payment_terms_days": pay_terms,
                "items_quoted": paired_count,
                "total_items_requested": total_items,
            }
        )

    scoring_result = calculate_scores(quotes_data, comparison.weights)
    winner_vendor_id = scoring_result["winner_vendor_id"]

    facts = {
        "comparison_id": str(comparison.id),
        "scores": scoring_result["scores"],
        "winner_vendor_id": winner_vendor_id,
        "is_close": scoring_result["is_close"],
        "margin": scoring_result["margin"],
    }

    explanation = generate_explained_recommendation(facts, writer=writer)

    comparison.scores = scoring_result["scores"]
    comparison.recommended_vendor_id = uuid.UUID(winner_vendor_id) if winner_vendor_id else None
    comparison.explanation = explanation
    comparison.status = "ready"
    comparison.updated_at = datetime.now(timezone.utc)
    db.flush()

    winner_name = ""
    if winner_vendor_id:
        winner_info = scoring_result["scores"].get(str(winner_vendor_id), {})
        winner_name = winner_info.get("vendor_name", "")

    record_audit(
        session=db,
        actor=principal,
        action="comparison.recommended",
        entity_type="comparison",
        entity_id=comparison.id,
        after={
            "winner_vendor_id": str(winner_vendor_id),
            "winner_name": winner_name,
            "scores": scoring_result["scores"],
        },
        reason="Recommendation and scores generated",
    )
    db.commit()

    return RecommendationResponse(
        scores=scoring_result["scores"],
        recommended_vendor_id=comparison.recommended_vendor_id or uuid.uuid4(),
        winner_name=winner_name,
        is_close=scoring_result["is_close"],
        margin=scoring_result["margin"],
        explanation=explanation,
    )


def record_decision(
    db: Session,
    comparison_id: uuid.UUID,
    decision: DecisionRequest,
    principal: Principal,
) -> ComparisonResponse:
    comparison = db.query(Comparison).filter(Comparison.id == comparison_id).first()
    if not comparison:
        raise ProblemException(
            status_code=404, code="NOT_FOUND", title="Not Found", detail="Comparison not found"
        )

    if comparison.recommended_vendor_id != decision.vendor_id:
        if not decision.override_reason or len(decision.override_reason.strip()) < 10:
            raise ProblemException(
                status_code=422,
                code="OVERRIDE_REASON_REQUIRED",
                title="Unprocessable Entity",
                detail=(
                    "An override reason of at least 10 characters is required "
                    "when choosing a non-recommended vendor"
                ),
            )

    comparison.chosen_vendor_id = decision.vendor_id
    comparison.override_reason = (
        decision.override_reason.strip() if decision.override_reason else None
    )
    comparison.status = "decided"
    comparison.updated_at = datetime.now(timezone.utc)
    db.flush()

    record_audit(
        session=db,
        actor=principal,
        action="comparison.decided",
        entity_type="comparison",
        entity_id=comparison.id,
        after={
            "chosen_vendor_id": str(decision.vendor_id),
            "override_reason": comparison.override_reason,
            "is_override": comparison.recommended_vendor_id != decision.vendor_id,
        },
        reason="Vendor selected for purchase order creation",
    )
    db.commit()

    return get_comparison(db, comparison.id, principal)
