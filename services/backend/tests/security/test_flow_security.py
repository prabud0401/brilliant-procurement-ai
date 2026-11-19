import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.models import ApprovalStep, PurchaseOrder, PurchaseRequest
from app.core.policy import Principal, get_current_principal
from app.main import app


def _make_principal(
    roles: list[str],
    user_id: uuid.UUID | None = None,
    dept_id: uuid.UUID | None = None,
    limit: Decimal = Decimal("0.00"),
) -> Principal:
    return Principal(
        id=user_id or uuid.uuid4(),
        email=f"user-{uuid.uuid4().hex[:6]}@demo.example",
        display_name="Test User",
        roles=roles,
        department_id=dept_id or uuid.uuid4(),
        department_name="Test Dept",
        approval_limit_aed=limit,
    )


@pytest.mark.security
def test_acceptance_s4_self_approval_blocked_sod() -> None:
    """S4: creator blocked from approving own request (403 SOD_BLOCKED); routes to one approver."""
    client = TestClient(app)

    creator_id = uuid.uuid4()
    dept_id = uuid.uuid4()
    step_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    creator_principal = _make_principal(
        roles=["requester", "buyer"],
        user_id=creator_id,
        dept_id=dept_id,
    )

    mock_pr = PurchaseRequest(
        id=pr_id,
        number="PR-S4-001",
        requester_id=creator_id,
        department_id=dept_id,
        title="S4 Self Request",
        status="submitted",
        total_aed=Decimal("3000.00"),
    )

    mock_step = ApprovalStep(
        id=step_id,
        subject_type="pr",
        subject_id=pr_id,
        sequence=1,
        tier=1,
        assigned_to=creator_id,  # Hypothetical scenario where creator was assigned
        status="pending",
    )

    def mock_db_dep() -> Any:
        db = MagicMockSession()
        db.query_map[ApprovalStep] = {step_id: mock_step}
        db.query_map[PurchaseRequest] = {pr_id: mock_pr}
        return db

    app.dependency_overrides[get_current_principal] = lambda: creator_principal
    app.dependency_overrides[get_db] = mock_db_dep

    try:
        resp = client.post(
            f"/api/v1/approvals/{step_id}/decision",
            json={"decision": "approve", "comment": "Trying to approve my own PR"},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["code"] == "SOD_BLOCKED"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.security
def test_self_approval_blocked_for_purchase_order() -> None:
    client = TestClient(app)

    creator_id = uuid.uuid4()
    dept_id = uuid.uuid4()
    step_id = uuid.uuid4()
    po_id = uuid.uuid4()

    creator_principal = _make_principal(
        roles=["buyer"],
        user_id=creator_id,
        dept_id=dept_id,
    )

    mock_po = PurchaseOrder(
        id=po_id,
        number="PO-S4-002",
        created_by=creator_id,
        department_id=dept_id,
        vendor_id=uuid.uuid4(),
        status="submitted",
        total=Decimal("4000.00"),
    )

    mock_step = ApprovalStep(
        id=step_id,
        subject_type="po",
        subject_id=po_id,
        sequence=1,
        tier=1,
        assigned_to=creator_id,
        status="pending",
    )

    def mock_db_dep() -> Any:
        db = MagicMockSession()
        db.query_map[ApprovalStep] = {step_id: mock_step}
        db.query_map[PurchaseOrder] = {po_id: mock_po}
        return db

    app.dependency_overrides[get_current_principal] = lambda: creator_principal
    app.dependency_overrides[get_db] = mock_db_dep

    try:
        resp = client.post(
            f"/api/v1/approvals/{step_id}/decision",
            json={"decision": "approve"},
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "SOD_BLOCKED"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.security
def test_over_limit_approval_blocked() -> None:
    client = TestClient(app)

    approver_id = uuid.uuid4()
    dept_id = uuid.uuid4()
    step_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    # Manager with 50,000 AED limit
    manager_principal = _make_principal(
        roles=["manager"],
        user_id=approver_id,
        dept_id=dept_id,
        limit=Decimal("50000.00"),
    )

    # PR is 80,000 AED
    mock_pr = PurchaseRequest(
        id=pr_id,
        number="PR-OVERLIMIT",
        requester_id=uuid.uuid4(),  # Different user
        department_id=dept_id,
        title="Big Request",
        status="submitted",
        total_aed=Decimal("80000.00"),
    )

    mock_step = ApprovalStep(
        id=step_id,
        subject_type="pr",
        subject_id=pr_id,
        sequence=1,
        tier=2,
        assigned_to=approver_id,
        status="pending",
    )

    def mock_db_dep() -> Any:
        db = MagicMockSession()
        db.query_map[ApprovalStep] = {step_id: mock_step}
        db.query_map[PurchaseRequest] = {pr_id: mock_pr}
        return db

    app.dependency_overrides[get_current_principal] = lambda: manager_principal
    app.dependency_overrides[get_db] = mock_db_dep

    try:
        resp = client.post(
            f"/api/v1/approvals/{step_id}/decision",
            json={"decision": "approve", "comment": "Trying to approve above my limit"},
        )
        assert resp.status_code == 403
        data = resp.json()
        assert data["code"] == "ABOVE_LIMIT"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.security
def test_admin_without_business_role_cannot_approve() -> None:
    client = TestClient(app)

    admin_principal = _make_principal(roles=["admin"])
    step_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    mock_pr = PurchaseRequest(
        id=pr_id,
        number="PR-ADMIN",
        requester_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        title="Test",
        status="submitted",
        total_aed=Decimal("1000.00"),
    )

    mock_step = ApprovalStep(
        id=step_id,
        subject_type="pr",
        subject_id=pr_id,
        sequence=1,
        tier=1,
        assigned_to=admin_principal.id,
        status="pending",
    )

    def mock_db_dep() -> Any:
        db = MagicMockSession()
        db.query_map[ApprovalStep] = {step_id: mock_step}
        db.query_map[PurchaseRequest] = {pr_id: mock_pr}
        return db

    app.dependency_overrides[get_current_principal] = lambda: admin_principal
    app.dependency_overrides[get_db] = mock_db_dep

    try:
        resp = client.post(
            f"/api/v1/approvals/{step_id}/decision",
            json={"decision": "approve"},
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "FORBIDDEN"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.security
def test_access_matrix_new_endpoints() -> None:
    client = TestClient(app)

    requester_principal = _make_principal(roles=["requester"])
    buyer_principal = _make_principal(roles=["buyer"])

    # 1. Requester cannot create PO -> 403
    app.dependency_overrides[get_current_principal] = lambda: requester_principal
    resp = client.post("/api/v1/purchase-orders", json={"comparison_id": str(uuid.uuid4())})
    assert resp.status_code == 403

    # 2. Requester cannot create comparison -> 403
    resp = client.post(
        "/api/v1/comparisons",
        json={
            "pr_id": str(uuid.uuid4()),
            "quote_document_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
        },
    )
    assert resp.status_code == 403

    # 3. Buyer cannot PUT /settings -> 403
    app.dependency_overrides[get_current_principal] = lambda: buyer_principal
    resp = client.put(
        "/api/v1/settings/thresholds",
        json={"value": {"test": "val"}},
    )
    assert resp.status_code == 403

    app.dependency_overrides.clear()


class MagicMockSession:
    """Minimal fake DB session for unit/security tests mocking model lookups."""

    def __init__(self) -> None:
        self.query_map: dict[type[Any], dict[uuid.UUID, Any]] = {}

    def query(self, model: type[Any]) -> Any:
        return _QueryProxy(self.query_map.get(model, {}))

    def add(self, obj: Any) -> None:
        pass

    def flush(self) -> None:
        pass

    def commit(self) -> None:
        pass


class _QueryProxy:
    def __init__(self, data: dict[uuid.UUID, Any], empty: bool = False) -> None:
        self.data = data
        self.empty = empty

    def filter(self, *args: Any, **kwargs: Any) -> "_QueryProxy":
        for arg in args:
            s = str(arg)
            if "sequence >" in s:
                has_greater = any(getattr(obj, "sequence", 1) > 1 for obj in self.data.values())
                if not has_greater:
                    return _QueryProxy(self.data, empty=True)
            if "sequence <" in s:
                has_less = any(getattr(obj, "sequence", 2) < 2 for obj in self.data.values())
                if not has_less:
                    return _QueryProxy(self.data, empty=True)
        return self

    def first(self) -> Any:
        if self.empty:
            return None
        if self.data:
            return next(iter(self.data.values()))
        return None

    def all(self) -> list[Any]:
        if self.empty:
            return []
        return list(self.data.values())

    def order_by(self, *args: Any) -> "_QueryProxy":
        return self
