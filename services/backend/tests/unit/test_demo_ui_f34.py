"""Unit tests for F34 Demo UI improvements:
- PO payload includes vendor_name and approval_steps
- approval-history payload returns approver names and decided_at
- audit list items include human entity_label for a document and a user
- documents-list filter returns confirmed, non-suspicious invoices
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.audit.router import resolve_audit_entity_labels
from app.core.policy import Principal
from app.documents.router import list_documents
from app.orders.po_service import get_approval_history
from app.orders.schemas import ApprovalStepHistoryResponse, POResponse, PRResponse


def _make_principal(roles: list[str]) -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="buyer@demo.example",
        display_name="Buyer User",
        roles=roles,
        department_id=uuid.uuid4(),
        department_name="Procurement",
        approval_limit_aed=Decimal("50000.00"),
    )


@pytest.mark.unit
def test_po_response_vendor_name_and_approval_steps() -> None:
    """POResponse supports vendor_name and approval_steps."""
    po_id = uuid.uuid4()
    vendor_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    step_id = uuid.uuid4()

    step = ApprovalStepHistoryResponse(
        id=step_id,
        sequence=1,
        tier=2,
        status="approved",
        approver_name="Mariam Demo-Manager",
        decided_by_name="Mariam Demo-Manager",
        department_name="Facilities",
        role="manager",
        decided_at=now,
        comment="Budget approved",
    )

    po_resp = POResponse(
        id=po_id,
        number="PO-2026-6D79D3",
        vendor_id=vendor_id,
        vendor_name="Gulf Line IT Trading",
        department_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        status="approved",
        subtotal=Decimal("27500.00"),
        vat=Decimal("1375.00"),
        total=Decimal("28875.00"),
        currency="AED",
        created_at=now,
        lines=[],
        approval_steps=[step],
    )

    assert po_resp.vendor_name == "Gulf Line IT Trading"
    assert len(po_resp.approval_steps) == 1
    assert po_resp.approval_steps[0].approver_name == "Mariam Demo-Manager"
    assert po_resp.approval_steps[0].decided_at == now


@pytest.mark.unit
def test_pr_response_approval_steps() -> None:
    """PRResponse supports approval_steps."""
    pr_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    step1 = ApprovalStepHistoryResponse(
        id=uuid.uuid4(),
        sequence=1,
        tier=2,
        status="approved",
        approver_name="Mariam Demo-Manager",
        department_name="Facilities",
        decided_at=now,
    )
    step2 = ApprovalStepHistoryResponse(
        id=uuid.uuid4(),
        sequence=2,
        tier=3,
        status="approved",
        approver_name="Khalid Demo-Manager",
        department_name="Projects",
        decided_at=now,
    )

    pr_resp = PRResponse(
        id=pr_id,
        number="PR-2026-427C5B",
        requester_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        title="Facilities Fit-out",
        status="approved",
        total_aed=Decimal("62800.00"),
        currency="AED",
        created_at=now,
        lines=[],
        approval_steps=[step1, step2],
    )

    assert len(pr_resp.approval_steps) == 2
    assert pr_resp.approval_steps[0].approver_name == "Mariam Demo-Manager"
    assert pr_resp.approval_steps[1].approver_name == "Khalid Demo-Manager"
    assert pr_resp.approval_steps[0].decided_at == now
    assert pr_resp.approval_steps[1].decided_at == now


@pytest.mark.unit
def test_get_approval_history_returns_names_and_timestamps() -> None:
    """get_approval_history returns sequence, approver names, and decided_at timestamps."""
    mock_db = MagicMock()
    subject_id = uuid.uuid4()

    user_mariam_id = uuid.uuid4()
    user_khalid_id = uuid.uuid4()
    now1 = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
    now2 = datetime(2026, 11, 20, 14, 0, tzinfo=timezone.utc)

    mock_step1 = MagicMock()
    mock_step1.id = uuid.uuid4()
    mock_step1.subject_type = "po"
    mock_step1.subject_id = subject_id
    mock_step1.sequence = 1
    mock_step1.tier = 2
    mock_step1.status = "approved"
    mock_step1.decided_by = user_mariam_id
    mock_step1.assigned_to = user_mariam_id
    mock_step1.decided_at = now1
    mock_step1.comment = "Approved by Facilities"

    mock_step2 = MagicMock()
    mock_step2.id = uuid.uuid4()
    mock_step2.subject_type = "po"
    mock_step2.subject_id = subject_id
    mock_step2.sequence = 2
    mock_step2.tier = 3
    mock_step2.status = "approved"
    mock_step2.decided_by = user_khalid_id
    mock_step2.assigned_to = user_khalid_id
    mock_step2.decided_at = now2
    mock_step2.comment = "Approved by Projects"

    mock_mariam = MagicMock()
    mock_mariam.id = user_mariam_id
    mock_mariam.display_name = "Mariam Demo-Manager"
    mock_mariam.department.name = "Facilities"
    role1 = MagicMock()
    role1.role = "manager"
    mock_mariam.roles = [role1]

    mock_khalid = MagicMock()
    mock_khalid.id = user_khalid_id
    mock_khalid.display_name = "Khalid Demo-Manager"
    mock_khalid.department.name = "Projects"
    role2 = MagicMock()
    role2.role = "manager"
    mock_khalid.roles = [role2]

    # Query setup
    steps_query = MagicMock()
    steps_query.filter.return_value.order_by.return_value.all.return_value = [
        mock_step1,
        mock_step2,
    ]

    users_query = MagicMock()
    users_query.filter.return_value.all.return_value = [mock_mariam, mock_khalid]

    mock_db.query.side_effect = [steps_query, users_query]

    history = get_approval_history(mock_db, "po", subject_id)

    assert len(history) == 2
    assert history[0].sequence == 1
    assert history[0].approver_name == "Mariam Demo-Manager"
    assert history[0].department_name == "Facilities"
    assert history[0].decided_at == now1
    assert history[0].comment == "Approved by Facilities"

    assert history[1].sequence == 2
    assert history[1].approver_name == "Khalid Demo-Manager"
    assert history[1].department_name == "Projects"
    assert history[1].decided_at == now2
    assert history[1].comment == "Approved by Projects"


@pytest.mark.unit
def test_resolve_audit_entity_labels_for_user_and_document() -> None:
    """resolve_audit_entity_labels provides human labels for document and user rows."""
    mock_db = MagicMock()

    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    vendor_id = uuid.uuid4()
    ext_id = uuid.uuid4()

    mock_row_user = MagicMock()
    mock_row_user.id = 1
    mock_row_user.entity_type = "user"
    mock_row_user.entity_id = user_id
    mock_row_user.after = None

    mock_row_doc = MagicMock()
    mock_row_doc.id = 2
    mock_row_doc.entity_type = "document"
    mock_row_doc.entity_id = doc_id
    mock_row_doc.after = None

    # db.execute calls:
    # 1. users: [(user_id, "Mariam Demo-Manager", "manager.facilities@demo-holdings.example")]
    # 2. docs: [(doc_id, vendor_id, "quote")]
    # 3. vendors: [(vendor_id, "Gulf Line IT Trading")]
    # 4. extractions: [(ext_id, doc_id)]
    # 5. fields: [(ext_id, "document_number", "Q-1042")]
    res_users = MagicMock()
    res_users.all.return_value = [
        (user_id, "Mariam Demo-Manager", "manager.facilities@demo-holdings.example")
    ]

    res_docs = MagicMock()
    res_docs.all.return_value = [(doc_id, vendor_id, "quote")]

    res_vendors = MagicMock()
    res_vendors.all.return_value = [(vendor_id, "Gulf Line IT Trading")]

    res_exts = MagicMock()
    res_exts.all.return_value = [(ext_id, doc_id)]

    res_fields = MagicMock()
    res_fields.all.return_value = [(ext_id, "document_number", "Q-1042")]

    mock_db.execute.side_effect = [res_users, res_docs, res_vendors, res_exts, res_fields]

    labels = resolve_audit_entity_labels(mock_db, [mock_row_user, mock_row_doc])

    assert labels[1] == "Mariam Demo-Manager"
    assert labels[2] == "Gulf Line IT Trading · Q-1042"


@pytest.mark.unit
def test_list_documents_filter_suspicious() -> None:
    """list_documents with suspicious=False filters out suspicious documents."""
    mock_db = MagicMock()

    doc_id = uuid.uuid4()
    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.vendor_id = None
    mock_doc.doc_type = "invoice"
    mock_doc.status = "confirmed"
    mock_doc.pages = 1
    mock_doc.size_bytes = 2048
    mock_doc.created_at = datetime.now(timezone.utc)
    mock_doc.duplicate_of = None
    mock_doc.suspicious = False
    mock_doc.pr_id = None

    res_docs = MagicMock()
    res_docs.scalars.return_value.all.return_value = [mock_doc]
    res_exts = MagicMock()
    res_exts.all.return_value = []

    mock_db.execute.side_effect = [res_docs, res_exts]

    principal = _make_principal(["buyer"])
    results = list_documents(
        doc_status="confirmed",
        doc_type="invoice",
        suspicious=False,
        limit=50,
        offset=0,
        db=mock_db,
        principal=principal,
    )

    assert len(results) == 1
    assert results[0].id == doc_id
    assert results[0].status == "confirmed"
    assert results[0].suspicious is False
