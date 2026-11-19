import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.orm import Session

from app.audit.service import record, verify_chain


@pytest.mark.integration
def test_app_user_cannot_update_delete_truncate_audit_log(
    app_user_session: Session,
) -> None:
    """As app_user, UPDATE, DELETE, and TRUNCATE on audit_log must fail."""
    # 1. Insert is allowed for app_user
    entry = record(
        session=app_user_session,
        actor=None,
        action="test.permission_check",
        entity_type="test_entity",
        entity_id=uuid.uuid4(),
        reason="Initial entry",
    )
    app_user_session.commit()
    assert entry.id is not None

    # 2. UPDATE must fail
    with pytest.raises((DBAPIError, ProgrammingError)) as exc_update:
        app_user_session.execute(
            text("UPDATE audit_log SET reason = 'tampered' WHERE id = :id"),
            {"id": entry.id},
        )
        app_user_session.commit()
    app_user_session.rollback()
    assert (
        "permission denied" in str(exc_update.value).lower()
        or "append-only" in str(exc_update.value).lower()
    )

    # 3. DELETE must fail
    with pytest.raises((DBAPIError, ProgrammingError)) as exc_delete:
        app_user_session.execute(
            text("DELETE FROM audit_log WHERE id = :id"),
            {"id": entry.id},
        )
        app_user_session.commit()
    app_user_session.rollback()
    assert (
        "permission denied" in str(exc_delete.value).lower()
        or "append-only" in str(exc_delete.value).lower()
    )

    # 4. TRUNCATE must fail
    with pytest.raises((DBAPIError, ProgrammingError)) as exc_trunc:
        app_user_session.execute(text("TRUNCATE audit_log"))
        app_user_session.commit()
    app_user_session.rollback()
    assert (
        "permission denied" in str(exc_trunc.value).lower()
        or "append-only" in str(exc_trunc.value).lower()
    )


@pytest.mark.integration
def test_audit_hash_chain_and_tampering_detection(db_session: Session) -> None:
    """Hash chain verifies; tampering a row as superuser makes verify_chain() fail."""
    # Clear audit_log for isolated chain verification
    db_session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_no_truncate"))
    db_session.execute(text("TRUNCATE audit_log RESTART IDENTITY"))
    db_session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_no_truncate"))
    db_session.commit()

    # Insert 3 entries
    record(
        session=db_session,
        actor=None,
        action="doc.uploaded",
        entity_type="doc",
        entity_id=uuid.uuid4(),
        after={"name": "quote1.pdf"},
    )
    e2 = record(
        session=db_session,
        actor=None,
        action="field.corrected",
        entity_type="field",
        entity_id=uuid.uuid4(),
        before={"val": "100"},
        after={"val": "105"},
    )
    record(
        session=db_session,
        actor=None,
        action="approval.approved",
        entity_type="pr",
        entity_id=uuid.uuid4(),
        reason="Approved by manager",
    )
    db_session.commit()

    # Chain should verify cleanly
    valid, err, count = verify_chain(db_session)
    assert valid is True
    assert err is None
    assert count == 3

    # Tamper with row 2 as superuser (temporarily disable trigger)
    db_session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_no_update_delete"))
    db_session.execute(
        text("UPDATE audit_log SET reason = 'unauthorized modification' WHERE id = :id"),
        {"id": e2.id},
    )
    db_session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_no_update_delete"))
    db_session.commit()

    # Verification must now fail!
    valid_after_tamper, err_after_tamper, count_after_tamper = verify_chain(db_session)
    assert valid_after_tamper is False
    assert err_after_tamper is not None
    assert "tampered" in err_after_tamper.lower() or "mismatch" in err_after_tamper.lower()
