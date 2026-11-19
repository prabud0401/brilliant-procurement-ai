import logging
import signal
import socket
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.models import Job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [worker] %(message)s",
)
logger = logging.getLogger("worker")

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

    logger.info("Claimed job %s (type=%s)", job.id, job.type)

    try:
        if job.type == "ping":
            logger.info("Executing ping job %s: payload=%s", job.id, job.payload)
            job.status = "completed"
            job.last_error = None
        elif job.type == "extract":
            from app.worker.job_runner import handle_extract_job

            handle_extract_job(session, job)
        else:
            logger.warning("Unknown job type %s for job %s", job.type, job.id)
            job.status = "failed"
            job.last_error = f"Unsupported job type: {job.type}"
    except Exception as exc:
        logger.exception("Error processing job %s: %s", job.id, exc)
        job.status = "failed"
        job.last_error = str(exc)

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
