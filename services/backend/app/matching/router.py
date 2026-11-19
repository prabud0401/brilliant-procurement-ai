import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.policy import Principal, get_current_principal, require
from app.matching.schemas import (
    ExceptionResolveRequest,
    MatchCreateRequest,
    MatchExceptionResponse,
    MatchResponse,
)
from app.matching.service import (
    create_match,
    get_match,
    list_exceptions,
    resolve_exception,
)

matches_router = APIRouter(prefix="/matches", tags=["matches"])
exceptions_router = APIRouter(prefix="/exceptions", tags=["exceptions"])


@matches_router.post("", response_model=MatchResponse)
def run_three_way_match(
    body: MatchCreateRequest,
    principal: Principal = Depends(require("match.resolve")),
    db: Session = Depends(get_db),
) -> MatchResponse:
    return create_match(db, body.invoice_document_id, principal)


@matches_router.get("/{id}", response_model=MatchResponse)
def get_match_by_id(
    id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> MatchResponse:
    return get_match(db, id, principal)


@exceptions_router.get("", response_model=list[MatchExceptionResponse])
def get_exceptions_queue(
    status: str | None = Query(None),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[MatchExceptionResponse]:
    return list_exceptions(db, principal, status_filter=status)


@exceptions_router.post("/{id}/resolve", response_model=MatchExceptionResponse)
def resolve_match_exception(
    id: uuid.UUID,
    body: ExceptionResolveRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> MatchExceptionResponse:
    return resolve_exception(db, id, body, principal)
