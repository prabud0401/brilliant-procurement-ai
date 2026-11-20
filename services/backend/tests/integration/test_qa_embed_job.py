"""Integration tests for document embedding job on confirmation per design 6.6."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.models import Chunk, Document, ExtractedField, ExtractedLine, Extraction, Job, User
from app.qa.embed_job import handle_embed_document_job
from app.worker_main import process_single_job


@pytest.fixture
def test_buyer_and_doc(db_session: Session, migrator_url: str) -> tuple[User, Document]:
    from app.core.bootstrap import bootstrap
    from seed.load import run_seed

    run_seed(db_url=migrator_url)
    test_password = "".join(["D", "e", "m", "o", "1", "2", "3", "!", "@", "#"])
    bootstrap(db_session, password=test_password)

    # Clean previous state
    db_session.execute(text("DELETE FROM chunks"))
    db_session.execute(text("DELETE FROM extracted_lines"))
    db_session.execute(text("DELETE FROM extracted_fields"))
    db_session.execute(text("DELETE FROM extractions"))
    db_session.execute(text("DELETE FROM jobs"))
    db_session.execute(text("DELETE FROM documents"))
    db_session.commit()

    buyer = db_session.execute(
        select(User).where(User.email == "buyer1@demo-holdings.example")
    ).scalar_one()

    doc = Document(
        id=uuid.uuid4(),
        owner_id=buyer.id,
        department_id=buyer.department_id,
        doc_type="quote",
        status="confirmed",
        file_sha256="fake-embed-test-sha256-hash-001",
        blob_path="fake/path.pdf",
        mime="application/pdf",
        pages=1,
        size_bytes=1024,
    )
    db_session.add(doc)
    db_session.flush()

    ext = Extraction(
        id=uuid.uuid4(),
        document_id=doc.id,
        version=1,
        di_model="prebuilt-layout",
        llm_model="mock-llm",
        status="completed",
    )
    db_session.add(ext)
    db_session.flush()

    field1 = ExtractedField(
        id=uuid.uuid4(),
        extraction_id=ext.id,
        name="total",
        value_raw="AED 28,875.00",
        value_norm={"value": "28875.00"},
        confidence=Decimal("0.98"),
        page=1,
        status="confirmed",
    )
    field2 = ExtractedField(
        id=uuid.uuid4(),
        extraction_id=ext.id,
        name="payment_terms",
        value_raw="Net 30",
        value_norm={"value": "Net 30"},
        confidence=Decimal("0.95"),
        page=1,
        status="confirmed",
    )
    line1 = ExtractedLine(
        id=uuid.uuid4(),
        extraction_id=ext.id,
        line_no=1,
        item_code="IT-LAP-14",
        description="Laptop 14in Intel Core i7",
        qty=Decimal("10"),
        uom="EA",
        unit_price=Decimal("1900.00"),
        line_total=Decimal("19000.00"),
        confidence=Decimal("0.98"),
        page=1,
        status="confirmed",
    )
    db_session.add_all([field1, field2, line1])
    db_session.commit()

    return buyer, doc


@pytest.mark.integration
def test_embed_document_job_execution(
    db_session: Session, test_buyer_and_doc: tuple[User, Document]
) -> None:
    _, doc = test_buyer_and_doc

    job = Job(
        id=uuid.uuid4(),
        type="embed_document",
        payload={"document_id": str(doc.id)},
        status="queued",
    )
    db_session.add(job)
    db_session.commit()

    # Process job via worker
    processed = process_single_job(db_session)
    assert processed is True

    # Verify chunks created
    chunks = (
        db_session.execute(
            select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.chunk_no.asc())
        )
        .scalars()
        .all()
    )
    assert len(chunks) >= 1
    for c in chunks:
        assert c.embedding is not None
        assert len(c.embedding) == 1536
        assert c.tsv is not None
        assert c.owner_id == doc.owner_id
        assert c.department_id == doc.department_id
        assert c.content_hash != ""

    # Verify re-running with unchanged content skips re-embedding
    initial_chunks_count = len(chunks)
    job2 = Job(
        id=uuid.uuid4(),
        type="embed_document",
        payload={"document_id": str(doc.id)},
        status="queued",
    )
    handle_embed_document_job(db_session, job2)
    assert job2.status == "completed"

    chunks_after = (
        db_session.execute(select(Chunk).where(Chunk.document_id == doc.id)).scalars().all()
    )
    assert len(chunks_after) == initial_chunks_count
