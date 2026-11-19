"""Worker job execution for extraction pipeline with retries and exponential backoff."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record as record_audit
from app.core.models import Document, Job
from app.extraction.service import run_extraction

logger = logging.getLogger("worker.job_runner")

MAX_JOB_ATTEMPTS = 3


def handle_extract_job(session: Session, job: Job) -> None:
    """Handle extraction job with exponential backoff retries."""
    doc_id_raw = job.payload.get("document_id")
    if not doc_id_raw:
        job.status = "failed"
        job.last_error = "Missing document_id in job payload"
        return

    doc_id = uuid.UUID(doc_id_raw)
    try:
        run_extraction(session, doc_id)
        job.status = "completed"
        job.last_error = None
        logger.info("Successfully completed extraction for document %s", doc_id)
    except Exception as exc:
        logger.exception("Extraction failed for document %s: %s", doc_id, exc)
        if job.attempts < MAX_JOB_ATTEMPTS:
            backoff_seconds = (2**job.attempts) * 2  # Exponential backoff
            job.status = "queued"
            job.run_after = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
            job.last_error = f"Attempt {job.attempts} failed: {exc}"
            logger.info(
                "Scheduled retry #%d for job %s in %d seconds",
                job.attempts + 1,
                job.id,
                backoff_seconds,
            )
        else:
            job.status = "failed"
            job.last_error = f"Max attempts ({MAX_JOB_ATTEMPTS}) exceeded: {exc}"
            doc = session.execute(
                select(Document).where(Document.id == doc_id)
            ).scalar_one_or_none()
            if doc:
                doc.status = "failed"
                record_audit(
                    session=session,
                    actor=None,
                    action="document.extract_failed",
                    entity_type="document",
                    entity_id=doc.id,
                    reason=str(exc),
                    after={"status": "failed", "error": str(exc)},
                )
            logger.error(
                "Job %s permanently failed after %d attempts for document %s",
                job.id,
                job.attempts,
                doc_id,
            )
