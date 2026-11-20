"""Hybrid retrieval (pgvector + Postgres full-text) with RRF per design 6.6."""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import false, func, select, text, true
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.ai.schemas import RetrievedChunk
from app.core.config import settings
from app.core.models import Chunk, Document, Setting, Vendor
from app.core.policy import Principal, ScopeRule, get_effective_scope
from app.qa.schemas import ScopeFilter

DEFAULT_RELEVANCE_FLOOR = 0.020


def get_relevance_floor(session: Session) -> float:
    """Retrieve relevance floor from settings table or fallback to default."""
    try:
        db_setting = session.execute(
            select(Setting).where(Setting.key == "qa_relevance_floor")
        ).scalar_one_or_none()
        if db_setting and isinstance(db_setting.value, (int, float, str)):
            return float(db_setting.value)
        if db_setting and isinstance(db_setting.value, dict) and "value" in db_setting.value:
            return float(db_setting.value["value"])
    except Exception:
        pass
    return getattr(settings, "QA_RELEVANCE_FLOOR", DEFAULT_RELEVANCE_FLOOR)


def build_permission_filter(principal: Principal) -> ColumnElement[bool]:
    """Build SQL WHERE condition enforcing document access per design 7.2.

    Requester: own documents
    Buyer: all documents
    Manager: own department
    Admin: none (403/empty)
    """
    scope = get_effective_scope(principal, "qa.ask")
    if scope == ScopeRule.ALL:
        return true()
    if scope == ScopeRule.OWN:
        return Document.owner_id == principal.id
    if scope == ScopeRule.DEPT:
        if principal.department_id:
            return Document.department_id == principal.department_id
        return Document.owner_id == principal.id

    return false()


def compute_document_title(doc_type: str, vendor_name: str | None, chunk_text: str) -> str:
    """Derive display title from document type, number and vendor name."""
    type_str = (doc_type or "document").title()
    num_match = re.search(r"\b(Q-\d+|PO-\d+|DN-\d+|INV-\d+|PR-\d+)\b", chunk_text, re.IGNORECASE)
    doc_num = num_match.group(1).upper() if num_match else ""

    parts: list[str] = []
    if doc_num:
        parts.append(f"{type_str} {doc_num}")
    else:
        parts.append(type_str)

    if vendor_name:
        parts.append(f"({vendor_name})")

    return " ".join(parts)


def hybrid_retrieve(
    session: Session,
    question: str,
    question_vector: list[float],
    principal: Principal,
    scope: ScopeFilter | None = None,
    relevance_floor: float | None = None,
    top_k: int = 8,
) -> list[RetrievedChunk]:
    """Retrieve top chunks using hybrid vector + FTS search combined with Reciprocal Rank Fusion."""
    perm_filter = build_permission_filter(principal)

    scope_conditions: list[Any] = []
    if scope:
        if scope.document_id:
            scope_conditions.append(Document.id == scope.document_id)
        if scope.pr_id:
            scope_conditions.append(Document.pr_id == scope.pr_id)
        if scope.vendor_id:
            scope_conditions.append(Document.vendor_id == scope.vendor_id)

    # 1. Vector Search Query
    vec_stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Chunk.page,
            Chunk.chunk_no,
            Chunk.text,
            Document.doc_type,
            Vendor.name.label("vendor_name"),
            Chunk.embedding.cosine_distance(question_vector).label("distance"),
        )
        .join(Document, Chunk.document_id == Document.id)
        .outerjoin(Vendor, Document.vendor_id == Vendor.id)
        .where(perm_filter)
    )
    for cond in scope_conditions:
        vec_stmt = vec_stmt.where(cond)

    vec_stmt = vec_stmt.order_by("distance").limit(20)
    vec_rows = session.execute(vec_stmt).all()

    # 2. Full-Text Search Query
    fts_rows: list[Any] = []
    # Build tsquery expression: try OR of keywords (length >= 3), fallback to plainto_tsquery
    words = [w for w in re.findall(r"[a-zA-Z0-9]+", question) if len(w) >= 3]
    ts_query_expr: Any = None
    if words:
        ts_query_expr = func.to_tsquery("english", " | ".join(words))
    else:
        cleaned_q = re.sub(r"[^\w\s]", " ", question).strip()
        if cleaned_q:
            ts_query_expr = func.plainto_tsquery("english", cleaned_q)

    if ts_query_expr is not None:
        fts_stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.page,
                Chunk.chunk_no,
                Chunk.text,
                Document.doc_type,
                Vendor.name.label("vendor_name"),
                func.ts_rank_cd(Chunk.tsv, ts_query_expr).label("rank"),
            )
            .join(Document, Chunk.document_id == Document.id)
            .outerjoin(Vendor, Document.vendor_id == Vendor.id)
            .where(perm_filter)
            .where(Chunk.tsv.op("@@")(ts_query_expr))
        )
        for cond in scope_conditions:
            fts_stmt = fts_stmt.where(cond)

        fts_stmt = fts_stmt.order_by(text("rank DESC")).limit(20)
        try:
            fts_rows = list(session.execute(fts_stmt).all())
        except Exception:
            fts_rows = []

    # 3. Reciprocal Rank Fusion (RRF)
    k_constant = 60.0
    rrf_scores: dict[uuid.UUID, float] = defaultdict(float)
    chunk_row_map: dict[uuid.UUID, Any] = {}

    for rank_idx, row in enumerate(vec_rows, start=1):
        cid = row.id
        rrf_scores[cid] += 1.0 / (k_constant + rank_idx)
        chunk_row_map[cid] = row

    for rank_idx, row in enumerate(fts_rows, start=1):
        cid = row.id
        rrf_scores[cid] += 1.0 / (k_constant + rank_idx)
        chunk_row_map[cid] = row

    if not rrf_scores:
        return []

    # 4. Check Relevance Floor
    floor = relevance_floor if relevance_floor is not None else get_relevance_floor(session)
    sorted_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    # Top score must exceed the relevance floor
    if sorted_candidates[0][1] < floor:
        return []

    # 5. Build Top K Retrieved Chunks
    results: list[RetrievedChunk] = []
    for cid, score in sorted_candidates[:top_k]:
        if score < floor:
            continue
        row = chunk_row_map[cid]
        title = compute_document_title(row.doc_type, row.vendor_name, row.text)
        results.append(
            RetrievedChunk(
                id=str(row.id),
                document_id=str(row.document_id),
                document_title=title,
                page=row.page,
                chunk_no=row.chunk_no,
                text=row.text,
                score=round(score, 5),
            )
        )

    return results
