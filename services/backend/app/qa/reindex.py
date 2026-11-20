"""Management command to (re)build chunks and embeddings for all confirmed documents."""

from __future__ import annotations

import logging
import sys
import uuid

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.models import Document, Job
from app.qa.embed_job import handle_embed_document_job

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] [qa.reindex] %(message)s"
)
logger = logging.getLogger("qa.reindex")


def reindex_all_confirmed_documents() -> int:
    """Find all confirmed documents and (re)generate their chunks and embeddings."""
    session = SessionLocal()
    count = 0
    try:
        stmt = (
            select(Document)
            .where(Document.status == "confirmed")
            .order_by(Document.created_at.asc())
        )
        documents = session.execute(stmt).scalars().all()
        logger.info("Found %d confirmed documents to (re)index.", len(documents))

        for doc in documents:
            logger.info("Reindexing document %s (type=%s)...", doc.id, doc.doc_type)
            dummy_job = Job(
                id=uuid.uuid4(),
                type="embed_document",
                payload={"document_id": str(doc.id)},
                status="queued",
            )
            handle_embed_document_job(session, dummy_job)
            session.commit()
            count += 1

        logger.info("Completed reindexing %d documents.", count)
        return count
    except Exception as exc:
        session.rollback()
        logger.exception("Reindexing failed: %s", exc)
        raise
    finally:
        session.close()


def main() -> None:
    try:
        count = reindex_all_confirmed_documents()
        print(f"Successfully reindexed {count} confirmed document(s).")
    except Exception as exc:
        print(f"Error reindexing documents: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
