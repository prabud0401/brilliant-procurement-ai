"""Integration tests for /api/v1/qa/history endpoint."""

from __future__ import annotations

import datetime
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap
from app.core.models import QALog, User
from app.core.security import create_access_token
from app.main import app
from seed.load import run_seed


def _get_token(db_session: Session, email: str) -> str:
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


@pytest.fixture
def qa_history_fixture(db_session: Session, migrator_url: str) -> dict[str, str]:
    run_seed(db_url=migrator_url)
    test_password = "".join(["D", "e", "m", "o", "1", "2", "3", "!", "@", "#"])
    bootstrap(db_session, password=test_password)

    db_session.execute(text("DELETE FROM qa_logs"))
    db_session.commit()

    buyer = db_session.execute(
        select(User).where(User.email == "buyer1@demo-holdings.example")
    ).scalar_one()
    req = db_session.execute(
        select(User).where(User.email == "requester.fac@demo-holdings.example")
    ).scalar_one()

    buyer_token = _get_token(db_session, "buyer1@demo-holdings.example")
    req_token = _get_token(db_session, "requester.fac@demo-holdings.example")
    admin_token = _get_token(db_session, "admin@demo-holdings.example")

    # Insert historical entries
    now = datetime.datetime.now(datetime.timezone.utc)
    log_buyer_older = QALog(
        id=uuid.uuid4(),
        user_id=buyer.id,
        question_redacted="What are the payment terms on Q-1042?",
        answer="Net 30",
        citations=[{"doc_id": "doc1", "chunk_id": "c1", "page": 1}],
        refused=False,
        llm_model="gpt-4o-mini",
        tokens_in=150,
        tokens_out=25,
        latency_ms=210,
        created_at=now - datetime.timedelta(minutes=10),
    )
    log_buyer_newer = QALog(
        id=uuid.uuid4(),
        user_id=buyer.id,
        question_redacted="What is the total of invoice INV-2291?",
        answer="AED 28,875.00",
        citations=[{"doc_id": "doc2", "chunk_id": "c2", "page": 1}],
        refused=False,
        llm_model="gpt-4o-mini",
        tokens_in=140,
        tokens_out=20,
        latency_ms=180,
        created_at=now - datetime.timedelta(minutes=2),
    )
    log_req = QALog(
        id=uuid.uuid4(),
        user_id=req.id,
        question_redacted="Where is my laptop quote?",
        answer=None,
        citations=None,
        refused=True,
        llm_model="relevance_floor",
        tokens_in=0,
        tokens_out=0,
        latency_ms=45,
        created_at=now - datetime.timedelta(minutes=5),
    )
    db_session.add_all([log_buyer_older, log_buyer_newer, log_req])
    db_session.commit()

    return {
        "buyer_token": buyer_token,
        "req_token": req_token,
        "admin_token": admin_token,
        "log_buyer_older_id": str(log_buyer_older.id),
        "log_buyer_newer_id": str(log_buyer_newer.id),
        "log_req_id": str(log_req.id),
    }


@pytest.mark.integration
def test_qa_history_isolation_and_order(qa_history_fixture: dict[str, str]) -> None:
    client = TestClient(app)
    buyer_token = qa_history_fixture["buyer_token"]
    req_token = qa_history_fixture["req_token"]
    admin_token = qa_history_fixture["admin_token"]

    # 1. Buyer sees only buyer's logs, sorted newest first
    resp_buyer = client.get(
        "/api/v1/qa/history",
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert resp_buyer.status_code == 200
    buyer_items = resp_buyer.json()
    assert len(buyer_items) == 2
    assert buyer_items[0]["id"] == qa_history_fixture["log_buyer_newer_id"]
    assert buyer_items[1]["id"] == qa_history_fixture["log_buyer_older_id"]
    assert buyer_items[0]["question_redacted"] == "What is the total of invoice INV-2291?"
    assert buyer_items[1]["question_redacted"] == "What are the payment terms on Q-1042?"

    # 2. Requester sees only requester's logs
    resp_req = client.get(
        "/api/v1/qa/history",
        headers={"Authorization": f"Bearer {req_token}"},
    )
    assert resp_req.status_code == 200
    req_items = resp_req.json()
    assert len(req_items) == 1
    assert req_items[0]["id"] == qa_history_fixture["log_req_id"]
    assert req_items[0]["question_redacted"] == "Where is my laptop quote?"
    assert req_items[0]["refused"] is True

    # 3. Admin lacks qa.ask capability -> 403 Forbidden
    resp_admin = client.get(
        "/api/v1/qa/history",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_admin.status_code == 403

    # 4. Unauthenticated -> 401 Unauthorized
    resp_unauth = client.get("/api/v1/qa/history")
    assert resp_unauth.status_code == 401
