"""Integration tests for QA hybrid retrieval with permission and scope filters."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai.providers.mock import MockEmbedder
from app.core.bootstrap import bootstrap
from app.core.models import Chunk, Document, PurchaseRequest, User, Vendor
from app.core.policy import Principal
from app.qa.retrieval import hybrid_retrieve
from app.qa.schemas import ScopeFilter
from seed.load import run_seed


@pytest.fixture
def retrieval_test_data(
    db_session: Session, migrator_url: str
) -> Generator[dict[str, object], None, None]:
    # Ensure seed master data and demo users exist
    run_seed(db_url=migrator_url)
    test_password = "".join(["D", "e", "m", "o", "1", "2", "3", "!", "@", "#"])
    bootstrap(db_session, password=test_password)

    # Clean existing chunks and docs
    db_session.execute(text("DELETE FROM chunks"))
    db_session.execute(text("DELETE FROM extracted_lines"))
    db_session.execute(text("DELETE FROM extracted_fields"))
    db_session.execute(text("DELETE FROM extractions"))
    db_session.execute(text("DELETE FROM jobs"))
    db_session.execute(text("DELETE FROM documents"))
    db_session.execute(text("DELETE FROM purchase_requests"))
    db_session.commit()

    # Fetch users
    req_fac = db_session.execute(
        select(User).where(User.email == "requester.fac@demo-holdings.example")
    ).scalar_one()
    req_it = db_session.execute(
        select(User).where(User.email == "requester.it@demo-holdings.example")
    ).scalar_one()
    mgr_fac = db_session.execute(
        select(User).where(User.email == "manager.facilities@demo-holdings.example")
    ).scalar_one()
    buyer = db_session.execute(
        select(User).where(User.email == "buyer1@demo-holdings.example")
    ).scalar_one()
    admin = db_session.execute(
        select(User).where(User.email == "admin@demo-holdings.example")
    ).scalar_one()

    vendors = db_session.execute(select(Vendor)).scalars().all()
    vendor_a = vendors[0]
    vendor_b = vendors[1]

    pr_it = PurchaseRequest(
        id=uuid.uuid4(),
        number="PR-RET-IT-001",
        title="IT Request",
        requester_id=req_it.id,
        department_id=req_it.department_id,
        status="approved",
        total_aed=Decimal("5000.00"),
    )
    db_session.add(pr_it)
    db_session.flush()

    # Doc 1: Facilities department, owned by requester.fac
    doc_fac = Document(
        id=uuid.uuid4(),
        owner_id=req_fac.id,
        department_id=req_fac.department_id,
        vendor_id=vendor_a.id,
        doc_type="quote",
        status="confirmed",
        file_sha256="retrieval-test-doc-fac-sha256-01",
        blob_path="retrieval/doc1.pdf",
        mime="application/pdf",
        pages=1,
        size_bytes=1024,
    )
    db_session.add(doc_fac)

    # Doc 2: IT department, owned by requester.it, linked to PR-IT-001
    doc_it = Document(
        id=uuid.uuid4(),
        owner_id=req_it.id,
        department_id=req_it.department_id,
        vendor_id=vendor_b.id,
        pr_id=pr_it.id,
        doc_type="invoice",
        status="confirmed",
        file_sha256="retrieval-test-doc-it-sha256-02",
        blob_path="retrieval/doc2.pdf",
        mime="application/pdf",
        pages=1,
        size_bytes=1024,
    )
    db_session.add(doc_it)
    db_session.flush()

    # Generate chunks with embeddings and TSV
    embedder = MockEmbedder()
    text_fac = "Gulf Line IT Trading quote Q-1042 for laptops total AED 28875 payment Net 30"
    text_it = "Falcon Office Supplies invoice INV-5001 for server equipment total AED 5000"

    emb_fac = embedder.embed([text_fac])[0]
    emb_it = embedder.embed([text_it])[0]

    chunk_fac = Chunk(
        id=uuid.uuid4(),
        document_id=doc_fac.id,
        chunk_no=1,
        page=1,
        text=text_fac,
        content_hash="ret-fac-hash-01",
        embedding=emb_fac,
        owner_id=req_fac.id,
        department_id=req_fac.department_id,
    )
    chunk_it = Chunk(
        id=uuid.uuid4(),
        document_id=doc_it.id,
        chunk_no=1,
        page=1,
        text=text_it,
        content_hash="ret-it-hash-02",
        embedding=emb_it,
        owner_id=req_it.id,
        department_id=req_it.department_id,
    )
    db_session.add(chunk_fac)
    db_session.add(chunk_it)
    db_session.flush()

    # Update TSV vectors in postgres
    db_session.execute(
        text("UPDATE chunks SET tsv = to_tsvector('english', text) WHERE id IN (:c1, :c2)"),
        {"c1": chunk_fac.id, "c2": chunk_it.id},
    )
    db_session.commit()

    try:
        yield {
            "req_fac": req_fac,
            "req_it": req_it,
            "mgr_fac": mgr_fac,
            "buyer": buyer,
            "admin": admin,
            "doc_fac": doc_fac,
            "doc_it": doc_it,
            "vendor_a": vendor_a,
            "vendor_b": vendor_b,
            "pr_it": pr_it,
            "chunk_fac": chunk_fac,
            "chunk_it": chunk_it,
            "embedder": embedder,
        }
    finally:
        db_session.execute(text("DELETE FROM chunks"))
        db_session.execute(text("DELETE FROM documents"))
        db_session.execute(text("DELETE FROM purchase_requests"))
        db_session.commit()


def _make_principal(user: User) -> Principal:
    roles = [r.role for r in user.roles]
    dept_name = user.department.name if user.department else None
    return Principal(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=roles,
        department_id=user.department_id,
        department_name=dept_name,
        approval_limit_aed=user.approval_limit_aed,
        is_demo=user.is_demo,
        active=user.active,
    )


@pytest.mark.integration
def test_retrieval_requester_sees_own_documents_only(
    db_session: Session, retrieval_test_data: dict[str, object]
) -> None:
    req_fac = retrieval_test_data["req_fac"]
    assert isinstance(req_fac, User)
    embedder = retrieval_test_data["embedder"]
    assert isinstance(embedder, MockEmbedder)
    doc_fac = retrieval_test_data["doc_fac"]
    assert isinstance(doc_fac, Document)
    doc_it = retrieval_test_data["doc_it"]
    assert isinstance(doc_it, Document)

    p_fac = _make_principal(req_fac)
    query = "laptops and equipment"
    q_vec = embedder.embed([query])[0]

    # Requester Facilities should only see chunk from doc_fac
    results = hybrid_retrieve(
        session=db_session,
        question=query,
        question_vector=q_vec,
        principal=p_fac,
        relevance_floor=0.010,
    )
    doc_ids = {r.document_id for r in results}
    assert str(doc_fac.id) in doc_ids
    assert str(doc_it.id) not in doc_ids


@pytest.mark.integration
def test_retrieval_manager_sees_department_chunks_only(
    db_session: Session, retrieval_test_data: dict[str, object]
) -> None:
    mgr_fac = retrieval_test_data["mgr_fac"]
    assert isinstance(mgr_fac, User)
    embedder = retrieval_test_data["embedder"]
    assert isinstance(embedder, MockEmbedder)
    doc_fac = retrieval_test_data["doc_fac"]
    assert isinstance(doc_fac, Document)
    doc_it = retrieval_test_data["doc_it"]
    assert isinstance(doc_it, Document)

    p_mgr = _make_principal(mgr_fac)
    query = "equipment total"
    q_vec = embedder.embed([query])[0]

    # Manager Facilities should see doc_fac (in Facilities) but not doc_it (in IT)
    results = hybrid_retrieve(
        session=db_session,
        question=query,
        question_vector=q_vec,
        principal=p_mgr,
        relevance_floor=0.010,
    )
    doc_ids = {r.document_id for r in results}
    assert str(doc_fac.id) in doc_ids
    assert str(doc_it.id) not in doc_ids


@pytest.mark.integration
def test_retrieval_buyer_sees_all_confirmed_documents(
    db_session: Session, retrieval_test_data: dict[str, object]
) -> None:
    buyer = retrieval_test_data["buyer"]
    assert isinstance(buyer, User)
    embedder = retrieval_test_data["embedder"]
    assert isinstance(embedder, MockEmbedder)
    doc_fac = retrieval_test_data["doc_fac"]
    assert isinstance(doc_fac, Document)
    doc_it = retrieval_test_data["doc_it"]
    assert isinstance(doc_it, Document)

    p_buyer = _make_principal(buyer)
    query = "equipment total"
    q_vec = embedder.embed([query])[0]

    # Buyer has ScopeRule.ALL and sees chunks across both departments
    results = hybrid_retrieve(
        session=db_session,
        question=query,
        question_vector=q_vec,
        principal=p_buyer,
        relevance_floor=0.010,
    )
    doc_ids = {r.document_id for r in results}
    assert str(doc_fac.id) in doc_ids
    assert str(doc_it.id) in doc_ids


@pytest.mark.integration
def test_retrieval_admin_sees_no_chunks(
    db_session: Session, retrieval_test_data: dict[str, object]
) -> None:
    admin = retrieval_test_data["admin"]
    assert isinstance(admin, User)
    embedder = retrieval_test_data["embedder"]
    assert isinstance(embedder, MockEmbedder)

    p_admin = _make_principal(admin)
    query = "laptops and equipment"
    q_vec = embedder.embed([query])[0]

    # Admin has ScopeRule.NONE for qa.ask -> empty results
    results = hybrid_retrieve(
        session=db_session,
        question=query,
        question_vector=q_vec,
        principal=p_admin,
        relevance_floor=0.001,
    )
    assert len(results) == 0


@pytest.mark.integration
def test_retrieval_scope_filters_narrow_results(
    db_session: Session, retrieval_test_data: dict[str, object]
) -> None:
    buyer = retrieval_test_data["buyer"]
    assert isinstance(buyer, User)
    embedder = retrieval_test_data["embedder"]
    assert isinstance(embedder, MockEmbedder)
    doc_fac = retrieval_test_data["doc_fac"]
    assert isinstance(doc_fac, Document)
    doc_it = retrieval_test_data["doc_it"]
    assert isinstance(doc_it, Document)
    pr_it = retrieval_test_data["pr_it"]
    assert isinstance(pr_it, PurchaseRequest)
    vendor_a = retrieval_test_data["vendor_a"]
    assert isinstance(vendor_a, Vendor)

    p_buyer = _make_principal(buyer)
    query = "equipment total"
    q_vec = embedder.embed([query])[0]

    # 1. Scope by document_id
    res_doc = hybrid_retrieve(
        session=db_session,
        question=query,
        question_vector=q_vec,
        principal=p_buyer,
        scope=ScopeFilter(document_id=doc_fac.id),
        relevance_floor=0.010,
    )
    assert len(res_doc) >= 1
    assert all(r.document_id == str(doc_fac.id) for r in res_doc)

    # 2. Scope by pr_id
    res_pr = hybrid_retrieve(
        session=db_session,
        question=query,
        question_vector=q_vec,
        principal=p_buyer,
        scope=ScopeFilter(pr_id=pr_it.id),
        relevance_floor=0.010,
    )
    assert len(res_pr) >= 1
    assert all(r.document_id == str(doc_it.id) for r in res_pr)

    # 3. Scope by vendor_id
    res_ven = hybrid_retrieve(
        session=db_session,
        question=query,
        question_vector=q_vec,
        principal=p_buyer,
        scope=ScopeFilter(vendor_id=vendor_a.id),
        relevance_floor=0.010,
    )
    assert len(res_ven) >= 1
    assert all(r.document_id == str(doc_fac.id) for r in res_ven)
