"""Q&A router implementing POST /qa/ask and GET /qa/history per design 3.4, 5.4, 7.2."""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.cost import check_daily_budget
from app.ai.factory import get_answer_writer, get_embedder
from app.audit.service import record as record_audit
from app.core.database import get_db
from app.core.errors import ProblemException
from app.core.models import Document, PurchaseRequest, QALog, Vendor
from app.core.policy import Principal, require, scope_filter
from app.extraction.injection_detector import scan_text_for_injection
from app.qa.grounding import verify_grounding
from app.qa.rate_limit import check_qa_rate_limit
from app.qa.redaction import redact_question
from app.qa.retrieval import hybrid_retrieve
from app.qa.schemas import (
    AnswerItem,
    Citation,
    QAHistoryItem,
    QuestionRequest,
    QuestionResponse,
)

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post("/ask", response_model=QuestionResponse)
def ask_question(
    req: QuestionRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require("qa.ask")),
) -> QuestionResponse:
    """Ask a question grounded in accessible procurement documents (design 3.4, 5.4)."""
    start_time = time.time()

    # 1. Length validation (spec: e.g. 500 chars)
    question = req.question.strip()
    if len(question) > 500:
        raise ProblemException(
            status_code=400,
            code="QUESTION_TOO_LONG",
            title="Question Too Long",
            detail="Question exceeds maximum allowed length of 500 characters",
        )

    # 2. Per-user rate limiting
    check_qa_rate_limit(principal.id)

    # 3. Redact question for logging
    question_redacted = redact_question(question)

    # 4. Prompt injection detection on user question (design 7.5, US-29)
    injection_flags = scan_text_for_injection(question, page=1)
    if injection_flags:
        record_audit(
            session=db,
            actor=principal,
            action="qa.injection_refused",
            entity_type="qa",
            entity_id=None,
            reason="Prompt injection pattern detected in question",
            after={"question_redacted": question_redacted},
        )
        latency_ms = int((time.time() - start_time) * 1000)
        qa_log = QALog(
            id=uuid.uuid4(),
            user_id=principal.id,
            question_redacted=question_redacted,
            answer=None,
            citations=None,
            refused=True,
            llm_model="injection_detector",
            prompt_version="prompts/qa_v1.md",
            tokens_in=0,
            tokens_out=0,
            latency_ms=latency_ms,
        )
        db.add(qa_log)
        db.commit()

        return QuestionResponse(
            answer=[],
            refused=True,
            refusal_reason="Question rejected as unsafe or prompt injection attempt",
        )

    # 5. Daily AI budget enforcement
    check_daily_budget(db)

    # 5b. Scope validation: if scope specifies target, verify existence and access
    if req.scope:
        if req.scope.document_id:
            doc = db.execute(
                select(Document).where(
                    Document.id == req.scope.document_id,
                    scope_filter(principal, "document.read", Document),
                )
            ).scalar_one_or_none()
            if not doc:
                raise ProblemException(
                    status_code=404,
                    code="NOT_FOUND",
                    title="Not Found",
                    detail=f"Document {req.scope.document_id} not found",
                )
        if req.scope.pr_id:
            pr = db.execute(
                select(PurchaseRequest).where(
                    PurchaseRequest.id == req.scope.pr_id,
                    scope_filter(principal, "pr.create_edit", PurchaseRequest),
                )
            ).scalar_one_or_none()
            if not pr:
                raise ProblemException(
                    status_code=404,
                    code="NOT_FOUND",
                    title="Not Found",
                    detail=f"Purchase request {req.scope.pr_id} not found",
                )
        if req.scope.vendor_id:
            vendor = db.execute(
                select(Vendor).where(Vendor.id == req.scope.vendor_id)
            ).scalar_one_or_none()
            if not vendor:
                raise ProblemException(
                    status_code=404,
                    code="NOT_FOUND",
                    title="Not Found",
                    detail=f"Vendor {req.scope.vendor_id} not found",
                )

    # 6. Embed question
    embedder = get_embedder()
    embeddings = embedder.embed([question])
    question_vector = embeddings[0] if embeddings else [0.0] * 1536

    # 7. Hybrid retrieval with permission & scope filter in SQL
    retrieved_chunks = hybrid_retrieve(
        session=db,
        question=question,
        question_vector=question_vector,
        principal=principal,
        scope=req.scope,
    )

    # 8. Refuse without calling LLM if no chunk passes the floor
    if not retrieved_chunks:
        latency_ms = int((time.time() - start_time) * 1000)
        qa_log = QALog(
            id=uuid.uuid4(),
            user_id=principal.id,
            question_redacted=question_redacted,
            answer=None,
            citations=None,
            refused=True,
            llm_model="relevance_floor",
            prompt_version="prompts/qa_v1.md",
            tokens_in=0,
            tokens_out=0,
            latency_ms=latency_ms,
        )
        db.add(qa_log)
        db.commit()

        return QuestionResponse(
            answer=[],
            refused=True,
            refusal_reason="I could not find this in the documents you have access to",
        )

    # 9. Call answer writer
    answer_writer = get_answer_writer()
    draft = answer_writer.answer(question, retrieved_chunks)

    if draft.refused or not draft.sentences:
        latency_ms = int((time.time() - start_time) * 1000)
        qa_log = QALog(
            id=uuid.uuid4(),
            user_id=principal.id,
            question_redacted=question_redacted,
            answer=None,
            citations=None,
            refused=True,
            llm_model=draft.model,
            prompt_version=draft.prompt_version,
            tokens_in=draft.tokens_in,
            tokens_out=draft.tokens_out,
            latency_ms=latency_ms,
        )
        db.add(qa_log)
        db.commit()

        return QuestionResponse(
            answer=[],
            refused=True,
            refusal_reason=draft.refusal_reason
            or "I could not find this in the documents you have access to",
        )

    # 10. Run Grounding Check (citations retrieved, numbers/dates/vendors in cited text)
    grounded_sentences = verify_grounding(draft.sentences, retrieved_chunks)

    if not grounded_sentences:
        latency_ms = int((time.time() - start_time) * 1000)
        qa_log = QALog(
            id=uuid.uuid4(),
            user_id=principal.id,
            question_redacted=question_redacted,
            answer=None,
            citations=None,
            refused=True,
            llm_model=draft.model,
            prompt_version=draft.prompt_version,
            tokens_in=draft.tokens_in,
            tokens_out=draft.tokens_out,
            latency_ms=latency_ms,
        )
        db.add(qa_log)
        db.commit()

        return QuestionResponse(
            answer=[],
            refused=True,
            refusal_reason="Information could not be grounded in cited documents",
        )

    # 11. Format grounded response
    chunk_map = {c.id: c for c in retrieved_chunks}
    answer_items: list[AnswerItem] = []
    citations_for_log: list[dict[str, Any]] = []

    for sentence in grounded_sentences:
        item_citations: list[Citation] = []
        for cid in sentence.chunk_ids:
            chunk = chunk_map.get(cid)
            if chunk:
                c_obj = Citation(
                    document_id=uuid.UUID(chunk.document_id),
                    title=chunk.document_title,
                    page=chunk.page,
                    chunk_id=chunk.id,
                )
                item_citations.append(c_obj)
                citations_for_log.append(
                    {
                        "document_id": str(c_obj.document_id),
                        "title": c_obj.title,
                        "page": c_obj.page,
                        "chunk_id": c_obj.chunk_id,
                    }
                )

        answer_items.append(
            AnswerItem(
                text=sentence.text,
                citations=item_citations,
            )
        )

    # 12. Save QA Log
    latency_ms = int((time.time() - start_time) * 1000)
    answer_text_summary = " ".join(item.text for item in answer_items)
    qa_log = QALog(
        id=uuid.uuid4(),
        user_id=principal.id,
        question_redacted=question_redacted,
        answer=answer_text_summary,
        citations={"items": citations_for_log},
        refused=False,
        llm_model=draft.model,
        prompt_version=draft.prompt_version,
        tokens_in=draft.tokens_in,
        tokens_out=draft.tokens_out,
        latency_ms=latency_ms,
    )
    db.add(qa_log)
    db.commit()

    return QuestionResponse(
        answer=answer_items,
        refused=False,
        refusal_reason=None,
    )


@router.get("/history", response_model=list[QAHistoryItem])
def get_qa_history(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require("qa.ask")),
) -> list[QAHistoryItem]:
    """Retrieve history of questions asked by the calling user (design 5.4, US-17)."""
    stmt = (
        select(QALog)
        .where(QALog.user_id == principal.id)
        .order_by(QALog.created_at.desc())
        .limit(100)
    )
    logs = db.execute(stmt).scalars().all()

    return [
        QAHistoryItem(
            id=log.id,
            question_redacted=log.question_redacted,
            answer=log.answer,
            citations=log.citations,
            refused=log.refused,
            created_at=log.created_at,
        )
        for log in logs
    ]
