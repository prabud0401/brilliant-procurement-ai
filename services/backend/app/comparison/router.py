import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.comparison.schemas import (
    ComparisonCreateRequest,
    ComparisonResponse,
    DecisionRequest,
    PairingUpdateItem,
    QuoteUpdateItem,
    RecommendationResponse,
    WeightsUpdateRequest,
)
from app.comparison.service import (
    compute_recommendation,
    create_comparison,
    get_comparison,
    record_decision,
    update_pairings,
    update_quote,
    update_weights,
)
from app.core.database import get_db
from app.core.policy import Principal, get_current_principal, require

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


@router.post("", response_model=ComparisonResponse)
def create_new_comparison(
    body: ComparisonCreateRequest,
    principal: Principal = Depends(require("comparison.write")),
    db: Session = Depends(get_db),
) -> ComparisonResponse:
    return create_comparison(db, body, principal)


@router.get("/{id}", response_model=ComparisonResponse)
def get_comparison_by_id(
    id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> ComparisonResponse:
    return get_comparison(db, id, principal)


@router.patch("/{id}/pairings", response_model=ComparisonResponse)
def patch_comparison_pairings(
    id: uuid.UUID,
    body: list[PairingUpdateItem],
    principal: Principal = Depends(require("comparison.write")),
    db: Session = Depends(get_db),
) -> ComparisonResponse:
    return update_pairings(db, id, body, principal)


@router.patch("/{id}/quotes/{document_id}", response_model=ComparisonResponse)
def patch_comparison_quote(
    id: uuid.UUID,
    document_id: uuid.UUID,
    body: QuoteUpdateItem,
    principal: Principal = Depends(require("comparison.write")),
    db: Session = Depends(get_db),
) -> ComparisonResponse:
    return update_quote(db, id, document_id, body, principal)


@router.put("/{id}/weights", response_model=ComparisonResponse)
def put_comparison_weights(
    id: uuid.UUID,
    body: WeightsUpdateRequest,
    principal: Principal = Depends(require("comparison.write")),
    db: Session = Depends(get_db),
) -> ComparisonResponse:
    return update_weights(db, id, body, principal)


@router.post("/{id}/recommendation", response_model=RecommendationResponse)
def generate_recommendation(
    id: uuid.UUID,
    principal: Principal = Depends(require("comparison.write")),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    return compute_recommendation(db, id, principal)


@router.post("/{id}/decision", response_model=ComparisonResponse)
def make_vendor_decision(
    id: uuid.UUID,
    body: DecisionRequest,
    principal: Principal = Depends(require("comparison.write")),
    db: Session = Depends(get_db),
) -> ComparisonResponse:
    return record_decision(db, id, body, principal)
