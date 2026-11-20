import logging
import signal
import socket
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.middleware import request_id_ctx
from app.core.models import Job
from app.observability import setup_observability

# Initialize observability (OpenTelemetry, correlation, log redaction)
setup_observability("worker")

logger = logging.getLogger("worker")
logger.setLevel(logging.INFO)

worker_id = f"worker-{socket.gethostname()}-{uuid.uuid4().hex[:6]}"
running = True


def handle_sigterm(signum: int, frame: Any) -> None:
    global running
    logger.info("Received termination signal %s. Shutting down gracefully...", signum)
    running = False


def process_single_job(session: Session) -> bool:
    """Process a single queued job using FOR UPDATE SKIP LOCKED.

    Returns True if a job was found and processed, False otherwise.
    """
    # Select next available job
    now = datetime.now(timezone.utc)
    job = (
        session.query(Job)
        .filter(
            Job.status == "queued",
            Job.run_after <= now,
        )
        .order_by(Job.run_after.asc())
        .with_for_update(skip_locked=True)
        .first()
    )

    if not job:
        session.rollback()
        return False

    job.status = "running"
    job.locked_by = worker_id
    job.locked_at = now
    job.attempts += 1
    session.flush()

    req_id: str | None = None
    if job.payload and isinstance(job.payload, dict):
        req_id = job.payload.get("request_id")
    token = request_id_ctx.set(req_id or uuid.uuid4().hex)

    logger.info("Claimed job %s (type=%s, request_id=%s)", job.id, job.type, req_id or "")

    try:
        if job.type == "ping":
            logger.info("Executing ping job %s: payload=%s", job.id, job.payload)
            job.status = "completed"
            job.last_error = None
        elif job.type == "extract":
            from app.worker.job_runner import handle_extract_job

            handle_extract_job(session, job)
        elif job.type == "embed_document":
            from app.qa.embed_job import handle_embed_document_job

            handle_embed_document_job(session, job)
        else:
            logger.warning("Unknown job type %s for job %s", job.type, job.id)
            job.status = "failed"
            job.last_error = f"Unsupported job type: {job.type}"
    except Exception as exc:
        logger.exception("Error processing job %s: %s", job.id, exc)
        job.status = "failed"
        job.last_error = str(exc)
    finally:
        request_id_ctx.reset(token)

    session.commit()
    return True


def run_worker(max_cycles: int | None = None, poll_interval: float = 1.0) -> None:
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    logger.info("Worker %s started. Polling jobs queue...", worker_id)
    cycles = 0

    while running:
        if max_cycles is not None and cycles >= max_cycles:
            break

        session = SessionLocal()
        try:
            processed = process_single_job(session)
        except Exception as exc:
            logger.error("Error during queue processing loop: %s", exc)
            processed = False
        finally:
            session.close()

        cycles += 1

        if not processed and running:
            # Sleep in small increments to be responsive to signals
            step = 0.1
            slept = 0.0
            while running and slept < poll_interval:
                time.sleep(step)
                slept += step

    logger.info("Worker %s stopped cleanly.", worker_id)


def main() -> None:
    run_worker()


if __name__ == "__main__":
    main()
