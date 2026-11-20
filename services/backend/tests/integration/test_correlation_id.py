"""Integration test for Request ID correlation across API, Worker, and Audit."""

from __future__ import annotations

import io
import logging
import uuid
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.factory import set_document_analyzer, set_llm_client
from app.ai.providers.replay import ReplayDocumentAnalyzer, ReplayLlmClient
from app.core.bootstrap import bootstrap
from app.core.models import AuditLog, Job, User
from app.core.security import create_access_token
from app.documents.storage import InMemoryBlobStorage, set_storage
from app.main import app
from app.worker_main import process_single_job
from tools.datagen.layouts import render_pdf_to_bytes
from tools.datagen.scenarios import get_all_scenarios


@pytest.fixture(autouse=True)
def setup_storage(db_session: Session, migrator_url: str) -> Generator[None, None, None]:
    storage = InMemoryBlobStorage()
    set_storage(storage)
    set_document_analyzer(ReplayDocumentAnalyzer())
    set_llm_client(ReplayLlmClient())

    from sqlalchemy import text

    from seed.load import run_seed

    run_seed(db_url=migrator_url)
    bootstrap(db_session, password="TestPassword123!")

    db_session.execute(text("DELETE FROM extracted_lines"))
    db_session.execute(text("DELETE FROM extracted_fields"))
    db_session.execute(text("DELETE FROM extractions"))
    db_session.execute(text("DELETE FROM injection_flags"))
    db_session.execute(text("DELETE FROM jobs"))
    db_session.execute(text("DELETE FROM documents"))
    db_session.commit()
    yield


@pytest.mark.integration
def test_correlation_id_traces_upload_job_worker_and_audit(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify one upload can be traced by a single request ID across services."""
    buyer = db_session.execute(
        select(User).where(User.email == "buyer1@demo-holdings.example")
    ).scalar_one()

    token, _ = create_access_token(
        user_id=buyer.id,
        email=buyer.email,
        roles=["buyer"],
        department_id=buyer.department_id,
    )

    scenarios = {s.doc_id: s for s in get_all_scenarios()}
    scenario = scenarios["s1-quote-gulfline"]
    pdf_bytes = render_pdf_to_bytes(scenario)

    trace_id = f"trace-corr-{uuid.uuid4().hex[:12]}"
    client = TestClient(app)

    # 1. API Upload with X-Request-ID
    with caplog.at_level(logging.INFO):
        res = client.post(
            "/api/v1/documents",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Request-ID": trace_id,
            },
            files={"file": ("quote_S1.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"doc_type": "quote"},
        )

    assert res.status_code == 202
    assert res.headers.get("X-Request-ID") == trace_id
    doc_id = uuid.UUID(res.json()["id"])

    # 2. Verify Job enqueued has request_id in payload
    job = db_session.execute(
        select(Job).where(Job.payload["document_id"].as_string() == str(doc_id))
    ).scalar_one()
    assert job.payload.get("request_id") == trace_id

    # 3. Verify upload audit entry has request_id
    upload_audit = db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_id == doc_id,
            AuditLog.action == "document.uploaded",
        )
    ).scalar_one()
    assert upload_audit.request_id == trace_id

    # 4. Run worker job and capture logs
    with caplog.at_level(logging.INFO):
        processed = process_single_job(db_session)
        assert processed is True

    # 5. Verify worker logs contain the trace correlation ID
    worker_log_records = [
        rec.getMessage()
        for rec in caplog.records
        if trace_id in rec.getMessage() or getattr(rec, "request_id", "") == trace_id
    ]
    assert len(worker_log_records) > 0, f"Expected {trace_id} in worker logs"

    # 6. Verify worker audit entries also carry the exact same request_id
    extract_audit = db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_id == doc_id,
            AuditLog.action == "document.extracted",
        )
    ).scalar_one()
    assert extract_audit.request_id == trace_id
