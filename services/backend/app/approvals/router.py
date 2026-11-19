import uuid

from fastapi import APIRouter, Depends
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

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/inbox", response_model=list[InboxItemResponse])
def list_inbox(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[InboxItemResponse]:
    return get_inbox(db, principal)


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
