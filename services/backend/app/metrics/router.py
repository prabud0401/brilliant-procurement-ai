"""Admin metrics router implementing GET /api/v1/admin/metrics per design 5.4, 9.1."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.policy import Principal, require
from app.metrics.schemas import AdminMetricsResponse
from app.metrics.service import compute_admin_metrics

router = APIRouter(prefix="/admin/metrics", tags=["admin-metrics"])


@router.get("", response_model=AdminMetricsResponse)
def get_admin_metrics(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require("admin.manage")),
) -> AdminMetricsResponse:
    """Retrieve operational and business observability metrics for Admin dashboard."""
    return compute_admin_metrics(db)
