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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import verify_chain
from app.core.database import get_db
from app.core.errors import ProblemException
from app.core.models import (
    ApprovalStep,
    AuditLog,
    Comparison,
    Document,
    ExtractedField,
    Extraction,
    Match,
    PurchaseOrder,
    PurchaseRequest,
    User,
    Vendor,
)
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
    entity_label: str | None = None
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


def resolve_audit_entity_labels(db: Session, rows: list[AuditLog]) -> dict[int, str | None]:
    labels: dict[int, str | None] = {}
    if not rows:
        return labels

    user_ids: set[uuid.UUID] = set()
    doc_ids: set[uuid.UUID] = set()
    pr_ids: set[uuid.UUID] = set()
    po_ids: set[uuid.UUID] = set()
    match_ids: set[uuid.UUID] = set()
    comp_ids: set[uuid.UUID] = set()
    step_ids: set[uuid.UUID] = set()

    for r in rows:
        if not r.entity_id:
            continue
        etype = r.entity_type
        if etype == "user":
            user_ids.add(r.entity_id)
        elif etype == "document":
            doc_ids.add(r.entity_id)
        elif etype in ("purchase_request", "pr"):
            pr_ids.add(r.entity_id)
        elif etype in ("purchase_order", "po"):
            po_ids.add(r.entity_id)
        elif etype == "match":
            match_ids.add(r.entity_id)
        elif etype == "comparison":
            comp_ids.add(r.entity_id)
        elif etype in ("pr_approval_step", "po_approval_step"):
            step_ids.add(r.entity_id)

    user_map: dict[uuid.UUID, str] = {}
    if user_ids:
        users = db.execute(
            select(User.id, User.display_name, User.email).where(User.id.in_(user_ids))
        ).all()
        user_map = {u[0]: (u[1] or u[2]) for u in users}

    pr_map: dict[uuid.UUID, str] = {}
    if pr_ids:
        prs = db.execute(
            select(PurchaseRequest.id, PurchaseRequest.number).where(PurchaseRequest.id.in_(pr_ids))
        ).all()
        pr_map = {p[0]: p[1] for p in prs}

    po_map: dict[uuid.UUID, str] = {}
    if po_ids:
        pos = db.execute(
            select(PurchaseOrder.id, PurchaseOrder.number).where(PurchaseOrder.id.in_(po_ids))
        ).all()
        po_map = {p[0]: p[1] for p in pos}

    doc_map: dict[uuid.UUID, str] = {}
    if doc_ids:
        docs = db.execute(
            select(Document.id, Document.vendor_id, Document.doc_type).where(
                Document.id.in_(doc_ids)
            )
        ).all()
        doc_vendor_ids = {d[1] for d in docs if d[1] is not None}
        vendors = (
            db.execute(select(Vendor.id, Vendor.name).where(Vendor.id.in_(doc_vendor_ids))).all()
            if doc_vendor_ids
            else []
        )
        vendor_name_map = {v[0]: v[1] for v in vendors}

        extractions = db.execute(
            select(Extraction.id, Extraction.document_id)
            .where(Extraction.document_id.in_(doc_ids))
            .order_by(Extraction.document_id, Extraction.version.desc())
        ).all()
        latest_ext_by_doc: dict[uuid.UUID, uuid.UUID] = {}
        for ext_id, ext_doc_id in extractions:
            if ext_doc_id not in latest_ext_by_doc:
                latest_ext_by_doc[ext_doc_id] = ext_id

        latest_ext_ids = list(latest_ext_by_doc.values())
        field_names = ("vendor_name", "document_number", "po_number", "quote_number")
        fields_by_ext_id: dict[uuid.UUID, dict[str, str]] = {}
        if latest_ext_ids:
            field_rows = db.execute(
                select(
                    ExtractedField.extraction_id, ExtractedField.name, ExtractedField.value_raw
                ).where(
                    ExtractedField.extraction_id.in_(latest_ext_ids),
                    ExtractedField.name.in_(field_names),
                )
            ).all()
            for ext_id, name, val in field_rows:
                if val is not None and val.strip():
                    fields_by_ext_id.setdefault(ext_id, {})[name] = val.strip()

        doc_type_labels: dict[str, str] = {
            "quote": "Quotation",
            "purchase_order": "Purchase Order",
            "delivery_note": "Delivery Note",
            "invoice": "Invoice",
            "other": "Document",
        }

        for d_id, d_vendor_id, d_type in docs:
            doc_ext_id = latest_ext_by_doc.get(d_id)
            ext_fields = fields_by_ext_id.get(doc_ext_id, {}) if doc_ext_id else {}
            v_name = (
                vendor_name_map.get(d_vendor_id)
                if (d_vendor_id and d_vendor_id in vendor_name_map)
                else ext_fields.get("vendor_name")
            )
            d_num = (
                ext_fields.get("document_number")
                or ext_fields.get("po_number")
                or ext_fields.get("quote_number")
            )
            fallback = doc_type_labels.get(d_type, "Document")
            if v_name and d_num:
                doc_map[d_id] = f"{v_name} · {d_num}"
            elif v_name:
                doc_map[d_id] = v_name
            elif d_num:
                doc_map[d_id] = d_num
            else:
                doc_map[d_id] = fallback

    match_map: dict[uuid.UUID, str] = {}
    if match_ids:
        matches = db.execute(
            select(Match.id, Match.invoice_document_id).where(Match.id.in_(match_ids))
        ).all()
        inv_doc_ids = {m[1] for m in matches if m[1] not in doc_map}
        if inv_doc_ids:
            inv_docs = db.execute(
                select(Document.id, Document.vendor_id, Document.doc_type).where(
                    Document.id.in_(inv_doc_ids)
                )
            ).all()
            inv_v_ids = {d[1] for d in inv_docs if d[1] is not None}
            inv_vendors = (
                db.execute(select(Vendor.id, Vendor.name).where(Vendor.id.in_(inv_v_ids))).all()
                if inv_v_ids
                else []
            )
            inv_v_map = {v[0]: v[1] for v in inv_vendors}
            inv_exts = db.execute(
                select(Extraction.id, Extraction.document_id)
                .where(Extraction.document_id.in_(inv_doc_ids))
                .order_by(Extraction.document_id, Extraction.version.desc())
            ).all()
            inv_latest_ext: dict[uuid.UUID, uuid.UUID] = {}
            for e_id, e_doc_id in inv_exts:
                if e_doc_id not in inv_latest_ext:
                    inv_latest_ext[e_doc_id] = e_id
            inv_ext_ids = list(inv_latest_ext.values())
            inv_fields: dict[uuid.UUID, dict[str, str]] = {}
            if inv_ext_ids:
                f_rows = db.execute(
                    select(
                        ExtractedField.extraction_id, ExtractedField.name, ExtractedField.value_raw
                    ).where(
                        ExtractedField.extraction_id.in_(inv_ext_ids),
                        ExtractedField.name.in_(("vendor_name", "document_number")),
                    )
                ).all()
                for e_id, n, val in f_rows:
                    if val and val.strip():
                        inv_fields.setdefault(e_id, {})[n] = val.strip()
            for d_id, d_v_id, _ in inv_docs:
                inv_doc_ext_id = inv_latest_ext.get(d_id)
                e_f = inv_fields.get(inv_doc_ext_id, {}) if inv_doc_ext_id else {}
                vn = (inv_v_map.get(d_v_id) if d_v_id else None) or e_f.get("vendor_name")
                dn = e_f.get("document_number")
                if vn and dn:
                    doc_map[d_id] = f"{vn} · {dn}"
                elif dn:
                    doc_map[d_id] = dn
                elif vn:
                    doc_map[d_id] = vn
                else:
                    doc_map[d_id] = "Invoice"

        for m_id, inv_doc_id in matches:
            if inv_doc_id in doc_map:
                match_map[m_id] = f"Match: {doc_map[inv_doc_id]}"

    comp_map: dict[uuid.UUID, str] = {}
    if comp_ids:
        comps = db.execute(
            select(Comparison.id, Comparison.pr_id).where(Comparison.id.in_(comp_ids))
        ).all()
        needed_pr_ids = {c[1] for c in comps if c[1] not in pr_map}
        if needed_pr_ids:
            c_prs = db.execute(
                select(PurchaseRequest.id, PurchaseRequest.number).where(
                    PurchaseRequest.id.in_(needed_pr_ids)
                )
            ).all()
            for cp_id, cp_num in c_prs:
                pr_map[cp_id] = cp_num
        for c_id, pr_id in comps:
            if pr_id in pr_map:
                comp_map[c_id] = f"Comparison for {pr_map[pr_id]}"
            else:
                comp_map[c_id] = "Quote Comparison"

    step_map: dict[uuid.UUID, str] = {}
    if step_ids:
        steps = db.execute(
            select(ApprovalStep.id, ApprovalStep.subject_type, ApprovalStep.subject_id).where(
                ApprovalStep.id.in_(step_ids)
            )
        ).all()
        for s_id, s_type, s_sub_id in steps:
            if s_type == "pr" and s_sub_id in pr_map:
                step_map[s_id] = f"Approval for {pr_map[s_sub_id]}"
            elif s_type == "po" and s_sub_id in po_map:
                step_map[s_id] = f"Approval for {po_map[s_sub_id]}"
            elif s_type == "pr":
                p_row = db.execute(
                    select(PurchaseRequest.number).where(PurchaseRequest.id == s_sub_id)
                ).first()
                if p_row:
                    step_map[s_id] = f"Approval for {p_row[0]}"
            elif s_type == "po":
                po_row = db.execute(
                    select(PurchaseOrder.number).where(PurchaseOrder.id == s_sub_id)
                ).first()
                if po_row:
                    step_map[s_id] = f"Approval for {po_row[0]}"

    for r in rows:
        if not r.entity_id:
            labels[r.id] = None
            continue
        etype = r.entity_type
        if etype == "user":
            labels[r.id] = (
                user_map.get(r.entity_id)
                or (r.after or {}).get("display_name")
                or (r.after or {}).get("email")
            )
        elif etype in ("purchase_request", "pr"):
            labels[r.id] = pr_map.get(r.entity_id) or (r.after or {}).get("number")
        elif etype in ("purchase_order", "po"):
            labels[r.id] = po_map.get(r.entity_id) or (r.after or {}).get("number")
        elif etype == "document":
            labels[r.id] = doc_map.get(r.entity_id)
        elif etype == "match":
            labels[r.id] = match_map.get(r.entity_id)
        elif etype == "comparison":
            labels[r.id] = comp_map.get(r.entity_id)
        elif etype in ("pr_approval_step", "po_approval_step"):
            labels[r.id] = step_map.get(r.entity_id)
        else:
            labels[r.id] = None

    return labels


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

    labels = resolve_audit_entity_labels(db, page_rows)

    items = [
        AuditItemResponse(
            id=r.id,
            occurred_at=r.occurred_at,
            actor_id=r.actor_id,
            actor_roles=r.actor_roles,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            entity_label=labels.get(r.id),
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
