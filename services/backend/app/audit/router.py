import base64
import csv
import io
import uuid
from collections.abc import Generator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.audit.service import verify_chain
from app.core.database import get_db
from app.core.errors import ProblemException
from app.core.models import AuditLog
from app.core.policy import Principal, require, scope_filter

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditItemResponse(BaseModel):
    id: int
    occurred_at: datetime
    actor_id: uuid.UUID | None
    actor_roles: list[str] | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    reason: str | None
    ai_model: str | None
    prompt_version: str | None
    request_id: str | None
    prev_hash: str | None
    hash: str

    model_config = ConfigDict(from_attributes=True)


class AuditListResponse(BaseModel):
    items: list[AuditItemResponse]
    next_cursor: str | None


class AuditVerifyResponse(BaseModel):
    valid: bool
    count: int
    error: str | None


def format_hex(data: bytes | None) -> str | None:
    return data.hex() if data else None


@router.get("", response_model=AuditListResponse)
def list_audit_logs(
    limit: int = Query(25, ge=1, le=100),
    cursor: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: uuid.UUID | None = Query(None),
    actor_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None),
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    principal: Principal = Depends(require("audit.view")),
    db: Session = Depends(get_db),
) -> AuditListResponse:
    query = db.query(AuditLog)

    # Apply RBAC record-level scope
    query = query.filter(scope_filter(principal, "audit.view", AuditLog))

    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if from_date:
        query = query.filter(AuditLog.occurred_at >= from_date)
    if to_date:
        query = query.filter(AuditLog.occurred_at <= to_date)

    if cursor:
        try:
            cursor_id = int(base64.urlsafe_b64decode(cursor.encode()).decode())
            query = query.filter(AuditLog.id < cursor_id)
        except Exception:
            raise ProblemException(
                status_code=400,
                code="INVALID_CURSOR",
                title="Bad Request",
                detail="Provided cursor is invalid",
            )

    rows = query.order_by(AuditLog.id.desc()).limit(limit + 1).all()

    next_cursor: str | None = None
    if len(rows) > limit:
        next_id = rows[limit - 1].id
        next_cursor = base64.urlsafe_b64encode(str(next_id).encode()).decode()
        page_rows = rows[:limit]
    else:
        page_rows = rows

    items = [
        AuditItemResponse(
            id=r.id,
            occurred_at=r.occurred_at,
            actor_id=r.actor_id,
            actor_roles=r.actor_roles,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            before=r.before,
            after=r.after,
            reason=r.reason,
            ai_model=r.ai_model,
            prompt_version=r.prompt_version,
            request_id=r.request_id,
            prev_hash=format_hex(r.prev_hash),
            hash=bytes(r.hash).hex(),
        )
        for r in page_rows
    ]

    return AuditListResponse(items=items, next_cursor=next_cursor)


@router.get("/verify", response_model=AuditVerifyResponse)
def verify_audit_chain(
    principal: Principal = Depends(require("audit.export")),
    db: Session = Depends(get_db),
) -> AuditVerifyResponse:
    valid, error_msg, count = verify_chain(db)
    return AuditVerifyResponse(valid=valid, count=count, error=error_msg)


@router.get("/export.csv")
def export_audit_csv(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    principal: Principal = Depends(require("audit.export")),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    query = db.query(AuditLog)
    if from_date:
        query = query.filter(AuditLog.occurred_at >= from_date)
    if to_date:
        query = query.filter(AuditLog.occurred_at <= to_date)

    rows = query.order_by(AuditLog.id.asc()).all()

    def generate_csv() -> Generator[str, None, None]:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "occurred_at",
                "actor_id",
                "actor_roles",
                "action",
                "entity_type",
                "entity_id",
                "before",
                "after",
                "reason",
                "ai_model",
                "prompt_version",
                "request_id",
                "prev_hash",
                "hash",
            ]
        )
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for r in rows:
            writer.writerow(
                [
                    r.id,
                    r.occurred_at.isoformat(),
                    str(r.actor_id) if r.actor_id else "",
                    ",".join(r.actor_roles) if r.actor_roles else "",
                    r.action,
                    r.entity_type,
                    str(r.entity_id) if r.entity_id else "",
                    r.before,
                    r.after,
                    r.reason or "",
                    r.ai_model or "",
                    r.prompt_version or "",
                    r.request_id or "",
                    format_hex(r.prev_hash) or "",
                    bytes(r.hash).hex(),
                ]
            )
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit_export.csv"'},
    )


@router.api_route(
    "/{path:path}",
    methods=["PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
@router.api_route(
    "",
    methods=["PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
def audit_mutations_blocked() -> None:
    raise ProblemException(
        status_code=405,
        code="METHOD_NOT_ALLOWED",
        title="Method Not Allowed",
        detail="Audit log is immutable and cannot be updated or deleted via API.",
    )
