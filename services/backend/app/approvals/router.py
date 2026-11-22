import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.approvals.schemas import (
    ApprovalBundleResponse,
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    InboxItemResponse,
)
from app.approvals.service import get_approval_bundle, get_inbox, record_decision
from app.core.database import get_db
from app.core.policy import Principal, get_current_principal
from app.orders.po_service import get_approval_history
from app.orders.schemas import ApprovalStepHistoryResponse

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/inbox", response_model=list[InboxItemResponse])
def list_inbox(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[InboxItemResponse]:
    return get_inbox(db, principal)


@router.get("/history", response_model=list[ApprovalStepHistoryResponse])
def list_approval_history(
    subject_type: str = Query(..., description="'pr' or 'po'"),
    subject_id: uuid.UUID = Query(...),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[ApprovalStepHistoryResponse]:
    return get_approval_history(db, subject_type, subject_id)


@router.get("/{step_id}", response_model=ApprovalBundleResponse)
def get_approval_step(
    step_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> ApprovalBundleResponse:
    return get_approval_bundle(db, step_id, principal)


@router.post("/{step_id}/decision", response_model=ApprovalDecisionResponse)
def make_approval_decision(
    step_id: uuid.UUID,
    body: ApprovalDecisionRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> ApprovalDecisionResponse:
    res = record_decision(
        db=db,
        step_id=step_id,
        decision=body.decision,
        comment=body.comment,
        principal=principal,
    )
    return ApprovalDecisionResponse(**res)
