import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.middleware import get_current_request_id
from app.core.models import AuditLog, User
from app.core.policy import Principal

AUDIT_ADVISORY_LOCK_ID = 8492049102938472


def canonical_row_json(
    occurred_at: datetime,
    actor_id: uuid.UUID | None,
    actor_roles: list[str] | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    reason: str | None,
    ai_model: str | None,
    prompt_version: str | None,
    request_id: str | None,
) -> bytes:
    """Generate deterministic canonical JSON for row hashing."""
    payload: dict[str, Any] = {
        "action": action,
        "actor_id": str(actor_id) if actor_id else None,
        "actor_roles": sorted(actor_roles) if actor_roles else [],
        "after": after,
        "ai_model": ai_model,
        "before": before,
        "entity_id": str(entity_id) if entity_id else None,
        "entity_type": entity_type,
        "occurred_at": occurred_at.astimezone(timezone.utc).isoformat(),
        "prompt_version": prompt_version,
        "reason": reason,
        "request_id": request_id,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def record(
    session: Session,
    actor: User | Principal | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
    ai_model: str | None = None,
    prompt_version: str | None = None,
    request_id: str | None = None,
    occurred_at: datetime | None = None,
) -> AuditLog:
    """Record an audit entry within transaction using an advisory lock to chain hashes."""
    # Transaction-level advisory lock serializes concurrent audit insertions
    session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"),
        {"lock_id": AUDIT_ADVISORY_LOCK_ID},
    )

    actor_id: uuid.UUID | None = None
    actor_roles: list[str] | None = None

    if actor is not None:
        actor_id = actor.id
        if isinstance(actor, Principal):
            actor_roles = sorted(actor.roles)
        elif isinstance(actor, User):
            actor_roles = sorted([r.role for r in actor.roles])

    ts = (occurred_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    req_id = request_id or get_current_request_id()

    # Get the latest row hash
    latest_row = session.execute(
        select(AuditLog.hash).order_by(AuditLog.id.desc()).limit(1)
    ).first()
    prev_hash: bytes = bytes(latest_row[0]) if latest_row and latest_row[0] else b""

    # Compute canonical JSON and new hash
    canonical_bytes = canonical_row_json(
        occurred_at=ts,
        actor_id=actor_id,
        actor_roles=actor_roles,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        reason=reason,
        ai_model=ai_model,
        prompt_version=prompt_version,
        request_id=req_id,
    )
    row_hash = hashlib.sha256(prev_hash + canonical_bytes).digest()

    entry = AuditLog(
        occurred_at=ts,
        actor_id=actor_id,
        actor_roles=actor_roles,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        reason=reason,
        ai_model=ai_model,
        prompt_version=prompt_version,
        request_id=req_id,
        prev_hash=prev_hash if prev_hash else None,
        hash=row_hash,
    )
    session.add(entry)
    session.flush()
    return entry


def verify_chain(session: Session) -> tuple[bool, str | None, int]:
    """Verify integrity of the audit log hash chain."""
    rows = session.query(AuditLog).order_by(AuditLog.id.asc()).all()
    expected_prev_hash: bytes = b""

    for idx, row in enumerate(rows):
        row_prev = bytes(row.prev_hash) if row.prev_hash else b""
        if row_prev != expected_prev_hash:
            return (
                False,
                f"Broken chain at id {row.id}: prev_hash does not match previous hash",
                idx,
            )

        canonical_bytes = canonical_row_json(
            occurred_at=row.occurred_at,
            actor_id=row.actor_id,
            actor_roles=row.actor_roles,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            before=row.before,
            after=row.after,
            reason=row.reason,
            ai_model=row.ai_model,
            prompt_version=row.prompt_version,
            request_id=row.request_id,
        )
        expected_hash = hashlib.sha256(expected_prev_hash + canonical_bytes).digest()
        row_hash = bytes(row.hash)
        if row_hash != expected_hash:
            return (
                False,
                f"Tampered record at id {row.id}: calculated hash does not match stored hash",
                idx,
            )

        expected_prev_hash = row_hash

    return True, None, len(rows)
