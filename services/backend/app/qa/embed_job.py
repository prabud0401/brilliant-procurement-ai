"""Worker job execution for document embedding per design 6.6."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.factory import get_embedder
from app.ai.schemas import OCRResult
from app.audit.service import record as record_audit
from app.core.models import Chunk, Document, Extraction, Job, Vendor
from app.documents.storage import get_storage
from app.qa.chunker import build_document_chunks

logger = logging.getLogger("qa.embed_job")


def handle_embed_document_job(session: Session, job: Job) -> None:
    """Worker handler for embed_document job."""
    doc_id_raw = job.payload.get("document_id")
    if not doc_id_raw:
        job.status = "failed"
        job.last_error = "Missing document_id in job payload"
        return

    doc_id = uuid.UUID(doc_id_raw)
    doc = session.execute(select(Document).where(Document.id == doc_id)).scalar_one_or_none()
    if not doc:
        job.status = "failed"
        job.last_error = f"Document {doc_id} not found"
        return

    # Load latest extraction
    extraction = (
        session.execute(
            select(Extraction)
            .where(Extraction.document_id == doc_id)
            .order_by(Extraction.version.desc())
        )
        .scalars()
        .first()
    )

    confirmed_fields: list[Any] = []
    confirmed_lines: list[Any] = []
    ocr_result: OCRResult | None = None

    if extraction:
        confirmed_fields = list(extraction.fields)
        confirmed_lines = list(extraction.lines)

        # Load raw OCR result if available
        if extraction.raw_ocr_path:
            try:
                storage = get_storage()
                raw_bytes = storage.download(extraction.raw_ocr_path)
                ocr_result = OCRResult.model_validate_json(raw_bytes)
            except Exception as exc:
                logger.warning(
                    "Could not load raw OCR from storage for document %s: %s",
                    doc_id,
                    exc,
                )

    # Load vendor name if linked
    vendor_name = None
    if doc.vendor_id:
        vendor = session.execute(
            select(Vendor).where(Vendor.id == doc.vendor_id)
        ).scalar_one_or_none()
        if vendor:
            vendor_name = vendor.name

    # Build chunks
    chunk_drafts = build_document_chunks(
        document=doc,
        ocr_result=ocr_result,
        confirmed_fields=confirmed_fields,
        confirmed_lines=confirmed_lines,
        vendor_name=vendor_name,
    )

    if not chunk_drafts:
        logger.info("No chunks produced for document %s", doc_id)
        job.status = "completed"
        return

    new_hash = chunk_drafts[0].content_hash

    # Check existing chunks for this document
    existing_chunks = (
        session.execute(select(Chunk).where(Chunk.document_id == doc_id)).scalars().all()
    )

    if existing_chunks and existing_chunks[0].content_hash == new_hash:
        logger.info(
            "Document %s content unchanged (hash=%s); skipping embedding",
            doc_id,
            new_hash[:8],
        )
        job.status = "completed"
        job.last_error = None
        return

    # Delete previous chunks if re-confirming changed content
    if existing_chunks:
        session.query(Chunk).filter(Chunk.document_id == doc_id).delete()
        session.flush()

    # Generate embeddings in one batch
    embedder = get_embedder()
    chunk_texts = [c.text for c in chunk_drafts]
    embeddings = embedder.embed(chunk_texts)

    # Persist chunks
    for draft, emb in zip(chunk_drafts, embeddings):
        chunk_row = Chunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            page=draft.page,
            chunk_no=draft.chunk_no,
            text=draft.text,
            embedding=emb,
            tsv=func.to_tsvector("english", draft.text),
            content_hash=draft.content_hash,
            owner_id=doc.owner_id,
            department_id=doc.department_id,
        )
        session.add(chunk_row)

    record_audit(
        session=session,
        actor=None,
        action="document.embedded",
        entity_type="document",
        entity_id=doc.id,
        after={"chunks_count": len(chunk_drafts), "content_hash": new_hash},
    )

    job.status = "completed"
    job.last_error = None
    logger.info(
        "Successfully embedded %d chunks for document %s (hash=%s)",
        len(chunk_drafts),
        doc.id,
        new_hash[:8],
    )
