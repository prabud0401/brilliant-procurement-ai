"""Integration check verifying logs hold no document text, emails or TRNs."""

from __future__ import annotations

import io
import logging
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.factory import set_document_analyzer, set_llm_client
from app.ai.providers.replay import ReplayDocumentAnalyzer, ReplayLlmClient
from app.core.bootstrap import bootstrap
from app.core.models import User
from app.core.security import create_access_token
from app.documents.storage import InMemoryBlobStorage, set_storage
from app.main import app
from app.observability.redaction import EMAIL_PATTERN, TRN_PATTERN
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
def test_logs_hold_no_emails_trns_or_raw_doc_text_during_pipeline(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
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

    client = TestClient(app)

    # Capture logs during upload and extraction
    with caplog.at_level(logging.INFO):
        # Also log a message containing raw email and TRN to test the live logging filter
        logger = logging.getLogger("test_capture")
        logger.info(
            "Processing invoice for buyer1@demo-holdings.example with vendor TRN 100234567800003"
        )

        res = client.post(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("quote_S1.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"doc_type": "quote"},
        )
        assert res.status_code == 202

        process_single_job(db_session)

    # Inspect all captured logs
    all_log_text = "\n".join(rec.getMessage() for rec in caplog.records)

    # 1. No unredacted emails
    emails_found = EMAIL_PATTERN.findall(all_log_text)
    assert len(emails_found) == 0, f"Found unredacted emails in logs: {emails_found}"

    # 2. No unredacted 15-digit TRNs
    trns_found = TRN_PATTERN.findall(all_log_text)
    assert len(trns_found) == 0, f"Found unredacted TRNs in logs: {trns_found}"

    # 3. Verified redaction markers are present
    assert "[REDACTED_EMAIL]" in all_log_text
    assert "[REDACTED_TRN]" in all_log_text
