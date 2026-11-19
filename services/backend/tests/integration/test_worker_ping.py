from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.core.models import Job
from app.worker_main import process_single_job


@pytest.mark.integration
def test_worker_processes_ping_job(db_session: Session) -> None:
    now = datetime.now(timezone.utc)
    job = Job(
        type="ping",
        payload={"ping_id": "test-123"},
        status="queued",
        run_after=now,
    )
    db_session.add(job)
    db_session.commit()

    job_id = job.id

    # Run one job processing cycle
    processed = process_single_job(db_session)
    assert processed is True

    # Refresh and verify job status
    db_session.expire_all()
    updated_job = db_session.query(Job).filter(Job.id == job_id).first()
    assert updated_job is not None
    assert updated_job.status == "completed"
    assert updated_job.locked_by is not None
    assert updated_job.locked_at is not None
    assert updated_job.attempts == 1
    assert updated_job.last_error is None

    # Processing again when queue has no jobs returns False
    second_processed = process_single_job(db_session)
    assert second_processed is False
