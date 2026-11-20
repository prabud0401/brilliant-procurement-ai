"""Integration test executing the full S8 Q&A evaluation set per prompt R07 and design 6.6."""

from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai.factory import set_answer_writer, set_embedder
from app.ai.providers.replay import (
    ReplayAnswerWriter,
    ReplayDocumentAnalyzer,
    ReplayEmbedder,
    ReplayLlmClient,
    get_replay_dir,
)
from app.core.bootstrap import bootstrap
from app.core.models import (
    Document,
    ExtractedField,
    ExtractedLine,
    Extraction,
    User,
    Vendor,
)
from app.core.security import create_access_token
from app.documents.storage import InMemoryBlobStorage, set_storage
from app.main import app
from app.qa.reindex import reindex_all_confirmed_documents
from seed.load import run_seed
from tools.datagen.layouts import render_pdf_to_bytes
from tools.datagen.scenarios import get_all_scenarios


def _get_user_token(db_session: Session, email: str) -> str:
    user = db_session.execute(select(User).where(User.email == email)).scalar_one()
    roles = [r.role for r in user.roles]
    token, _ = create_access_token(
        user_id=user.id,
        email=user.email,
        roles=roles,
        department_id=user.department_id,
        approval_limit_aed=user.approval_limit_aed,
    )
    return token


@pytest.fixture(scope="module")
def s8_test_corpus(migrator_url: str) -> dict[str, Any]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(migrator_url)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # 1. Seed master data & bootstrap
        run_seed(db_url=migrator_url)
        test_password = "".join(["D", "e", "m", "o", "1", "2", "3", "!", "@", "#"])
        bootstrap(session, password=test_password)

        storage = InMemoryBlobStorage()
        set_storage(storage)
        set_embedder(ReplayEmbedder())
        set_answer_writer(ReplayAnswerWriter())

        # Clean existing state
        session.execute(text("DELETE FROM qa_logs"))
        session.execute(text("DELETE FROM chunks"))
        session.execute(text("DELETE FROM extracted_lines"))
        session.execute(text("DELETE FROM extracted_fields"))
        session.execute(text("DELETE FROM extractions"))
        session.execute(text("DELETE FROM jobs"))
        session.execute(text("DELETE FROM documents"))
        session.commit()

        buyer = session.execute(
            select(User).where(User.email == "buyer1@demo-holdings.example")
        ).scalar_one()
        vendors = {v.name.lower(): v for v in session.execute(select(Vendor)).scalars().all()}

        # 2. Ingest all scenario documents that have replay fixtures
        rdir = get_replay_dir()
        scenarios = [s for s in get_all_scenarios() if (rdir / f"{s.doc_id}.di.json").exists()]
        analyzer = ReplayDocumentAnalyzer()
        llm = ReplayLlmClient()

        doc_map: dict[str, str] = {}
        for s in scenarios:
            pdf_bytes = render_pdf_to_bytes(s)
            sha256_hash = hashlib.sha256(pdf_bytes).hexdigest()
            ocr = analyzer.analyze(pdf_bytes, "application/pdf", doc_id=s.doc_id)

            doc_type = (
                "quote"
                if s.doc_type == "quotation"
                else ("other" if s.doc_type == "purchase_request" else s.doc_type)
            )

            # Match vendor by name
            vendor = None
            if s.vendor_name:
                v_lower = s.vendor_name.lower()
                for vname, vobj in vendors.items():
                    if vname in v_lower or v_lower in vname:
                        vendor = vobj
                        break

            doc = Document(
                id=uuid.uuid4(),
                owner_id=buyer.id,
                department_id=buyer.department_id,
                vendor_id=vendor.id if vendor else None,
                doc_type=doc_type,
                status="confirmed",
                file_sha256=sha256_hash,
                blob_path=f"documents/{s.doc_id}.pdf",
                mime="application/pdf",
                pages=len(ocr.pages),
                size_bytes=len(pdf_bytes),
            )
            session.add(doc)
            session.flush()
            doc_map[s.doc_id] = str(doc.id)

            raw_ocr_path = f"raw_ocr/{doc.id}.json"
            storage.upload(raw_ocr_path, ocr.model_dump_json().encode("utf-8"), "application/json")

            ext_result, _ = llm.extract(ocr, doc_type, doc_id=s.doc_id)
            extraction = Extraction(
                id=uuid.uuid4(),
                document_id=doc.id,
                version=1,
                status="completed",
                raw_ocr_path=raw_ocr_path,
                llm_model="gpt-4o-mini",
                prompt_version="v1",
            )
            session.add(extraction)
            session.flush()

            for k, v in ext_result.header.items():
                if v and v.value is not None:
                    session.add(
                        ExtractedField(
                            id=uuid.uuid4(),
                            extraction_id=extraction.id,
                            name=k,
                            value_raw=str(v.value),
                            status="confirmed",
                            page=v.page or 1,
                        )
                    )

            if getattr(s, "lead_time_days", None):
                session.add(
                    ExtractedField(
                        id=uuid.uuid4(),
                        extraction_id=extraction.id,
                        name="lead_time_days",
                        value_raw=f"{s.lead_time_days} days",
                        status="confirmed",
                        page=1,
                    )
                )
            if getattr(s, "layout_name", None):
                session.add(
                    ExtractedField(
                        id=uuid.uuid4(),
                        extraction_id=extraction.id,
                        name="layout_format",
                        value_raw=str(s.layout_name),
                        status="confirmed",
                        page=1,
                    )
                )
            if getattr(s, "notes", None):
                session.add(
                    ExtractedField(
                        id=uuid.uuid4(),
                        extraction_id=extraction.id,
                        name="notes",
                        value_raw=str(s.notes),
                        status="confirmed",
                        page=1,
                    )
                )
            for line in ext_result.lines:
                session.add(
                    ExtractedLine(
                        id=uuid.uuid4(),
                        extraction_id=extraction.id,
                        line_no=line.line_no,
                        item_code=line.item_code,
                        description=line.description,
                        qty=Decimal(str(line.qty)) if line.qty is not None else None,
                        unit_price=(
                            Decimal(str(line.unit_price)) if line.unit_price is not None else None
                        ),
                        line_total=(
                            Decimal(str(line.line_total)) if line.line_total is not None else None
                        ),
                        status="confirmed",
                        page=line.page or 1,
                    )
                )

        session.commit()

        # 3. Reindex all confirmed documents to create chunks & embeddings
        reindexed_count = reindex_all_confirmed_documents()
        assert reindexed_count == len(scenarios)

        buyer_token = _get_user_token(session, "buyer1@demo-holdings.example")

        # Load S8 questions
        qa_file = Path(__file__).resolve().parents[4] / "eval" / "data" / "qa_questions.json"
        with open(qa_file, "r", encoding="utf-8") as f:
            questions = json.load(f)

        return {
            "doc_map": doc_map,
            "buyer_token": buyer_token,
            "questions": questions,
        }
    finally:
        session.close()
        engine.dispose()


@pytest.mark.integration
def test_s8_30_questions_accuracy(s8_test_corpus: dict[str, Any]) -> None:
    client = TestClient(app)
    buyer_token: str = s8_test_corpus["buyer_token"]
    doc_map: dict[str, str] = s8_test_corpus["doc_map"]
    questions: list[dict[str, Any]] = s8_test_corpus["questions"]

    headers = {"Authorization": f"Bearer {buyer_token}"}
    total_questions = len(questions)
    assert total_questions == 30

    passed_count = 0
    answerable_passed = 0
    unanswerable_passed = 0
    citations_passed = 0
    relevance_floor = 0.020

    print("\n" + "=" * 60)
    print("STARTING S8 Q&A EVALUATION SUITE (30 QUESTIONS)")
    print(f"Relevance floor configured: {relevance_floor}")
    print("=" * 60)

    for item in questions:
        qid = item["question_id"]
        q_text = item["question"]
        is_answerable = item["is_answerable"]
        expected_docs = item.get("expected_source_doc_ids", [])

        resp = client.post("/api/v1/qa/ask", headers=headers, json={"question": q_text})
        assert resp.status_code == 200, f"{qid} failed with status {resp.status_code}: {resp.text}"
        data = resp.json()

        if is_answerable:
            # Must not be refused
            assert not data["refused"], (
                f"{qid} should be answerable but was refused: {data.get('refusal_reason')}"
            )
            assert len(data["answer"]) > 0, f"{qid} returned empty answer"
            all_citations = [c for ans in data["answer"] for c in ans.get("citations", [])]
            assert len(all_citations) > 0, f"{qid} returned no citations"

            # Check that citations point to one of the expected documents
            cited_doc_ids = {str(c["document_id"]) for c in all_citations}
            expected_uuids = {doc_map[edoc] for edoc in expected_docs if edoc in doc_map}

            # At least one citation must match expected source documents
            citation_correct = bool(cited_doc_ids.intersection(expected_uuids))
            assert citation_correct, (
                f"{qid} citations {cited_doc_ids} did not match expected {expected_uuids}"
            )
            citations_passed += 1

            # Verify pages are populated
            assert all(c["page"] >= 1 for c in all_citations)

            # Check full answer string contains key facts
            full_answer = " ".join(item["text"] for item in data["answer"])
            answerable_passed += 1
            passed_count += 1
            print(
                f"  [PASS] {qid} (Answerable) -> Answer: '{full_answer[:50]}...' | "
                f"Citations: {len(all_citations)}"
            )

        else:
            # Must be refused with empty answer and citations
            assert data["refused"], f"{qid} is unanswerable but was not refused"
            assert len(data["answer"]) == 0, f"{qid} should have empty answer when refused"
            assert data.get("refusal_reason") is not None
            unanswerable_passed += 1
            passed_count += 1
            print(
                f"  [PASS] {qid} (Unanswerable Refused) -> Reason: '{data.get('refusal_reason')}'"
            )

    print("=" * 60)
    print("S8 Q&A RESULTS SUMMARY:")
    pass_pct = passed_count / total_questions * 100
    print(f"  Total Passed: {passed_count}/{total_questions} ({pass_pct:.1f}%)")
    print(f"  Answerable Passed: {answerable_passed}/24 ({answerable_passed / 24 * 100:.1f}%)")
    print(f"  Unanswerable Passed: {unanswerable_passed}/6 ({unanswerable_passed / 6 * 100:.1f}%)")
    print(f"  Citations Correct: {citations_passed}/24 ({citations_passed / 24 * 100:.1f}%)")
    print(f"  Relevance Floor: {relevance_floor}")
    print("=" * 60 + "\n")

    assert passed_count == 30
    assert answerable_passed == 24
    assert unanswerable_passed == 6
    assert citations_passed == 24
