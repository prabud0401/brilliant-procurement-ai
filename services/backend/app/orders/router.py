import uuid

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ProblemException
from app.core.policy import Principal, get_current_principal, require
from app.orders.po_service import (
    create_po_from_comparison,
    get_approval_history,
    get_po,
    list_pos,
    push_po_to_odoo,
    submit_po,
)
from app.orders.pr_service import create_pr, get_pr, list_prs, submit_pr, update_pr
from app.orders.schemas import (
    ApprovalStepHistoryResponse,
    POCreateRequest,
    POPushResponse,
    POResponse,
    PRCreateRequest,
    PRResponse,
    PRUpdateRequest,
)

pr_router = APIRouter(prefix="/purchase-requests", tags=["purchase-requests"])
po_router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


# --- Purchase Requests Endpoints ---


@pr_router.post("", response_model=PRResponse)
def create_purchase_request(
    body: PRCreateRequest,
    principal: Principal = Depends(require("pr.create_edit")),
    db: Session = Depends(get_db),
) -> PRResponse:
    return create_pr(db, body, principal)


@pr_router.get("", response_model=list[PRResponse])
def list_purchase_requests(
    status: str | None = Query(None),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[PRResponse]:
    return list_prs(db, principal, status_filter=status)


@pr_router.get("/{id}", response_model=PRResponse)
def get_purchase_request(
    id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> PRResponse:
    return get_pr(db, id, principal)


@pr_router.get("/{id}/approval-history", response_model=list[ApprovalStepHistoryResponse])
def get_purchase_request_approval_history(
    id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[ApprovalStepHistoryResponse]:
    # Scope check matches get_pr
    get_pr(db, id, principal)
    return get_approval_history(db, "pr", id)


@pr_router.patch("/{id}", response_model=PRResponse)
def update_purchase_request(
    id: uuid.UUID,
    body: PRUpdateRequest,
    principal: Principal = Depends(require("pr.create_edit")),
    db: Session = Depends(get_db),
) -> PRResponse:
    return update_pr(db, id, body, principal)


@pr_router.post("/{id}/submit", response_model=PRResponse)
def submit_purchase_request(
    id: uuid.UUID,
    principal: Principal = Depends(require("pr.submit")),
    db: Session = Depends(get_db),
) -> PRResponse:
    return submit_pr(db, id, principal)


# --- Purchase Orders Endpoints ---


@po_router.post("", response_model=POResponse)
def create_purchase_order(
    body: POCreateRequest,
    principal: Principal = Depends(require("po.create")),
    db: Session = Depends(get_db),
) -> POResponse:
    return create_po_from_comparison(db, body, principal)


@po_router.get("", response_model=list[POResponse])
def list_purchase_orders(
    status: str | None = Query(None),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[POResponse]:
    return list_pos(db, principal, status_filter=status)


@po_router.get("/{id}", response_model=POResponse)
def get_purchase_order(
    id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> POResponse:
    return get_po(db, id, principal)


@po_router.get("/{id}/approval-history", response_model=list[ApprovalStepHistoryResponse])
def get_purchase_order_approval_history(
    id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[ApprovalStepHistoryResponse]:
    # Scope check matches get_po
    get_po(db, id, principal)
    return get_approval_history(db, "po", id)


@po_router.post("/{id}/submit", response_model=POResponse)
def submit_purchase_order(
    id: uuid.UUID,
    principal: Principal = Depends(require("po.create")),
    db: Session = Depends(get_db),
) -> POResponse:
    return submit_po(db, id, principal)


@po_router.post("/{id}/push-to-odoo", response_model=POPushResponse)
def push_purchase_order_to_odoo(
    id: uuid.UUID,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
    principal: Principal = Depends(require("po.create")),
    db: Session = Depends(get_db),
) -> POPushResponse:
    key = idempotency_key or x_idempotency_key
    if not key:
        raise ProblemException(
            status_code=422,
            code="IDEMPOTENCY_KEY_REQUIRED",
            title="Unprocessable Entity",
            detail="Header 'Idempotency-Key' is required",
        )
    return push_po_to_odoo(db, id, key, principal)
