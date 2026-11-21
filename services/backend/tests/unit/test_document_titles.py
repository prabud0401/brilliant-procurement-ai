"""Unit tests for document titles and DocumentSummary vendor_name / document_number fields (F31)."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.core.policy import Principal
from app.documents.router import DocumentSummary, list_documents
from app.matching.schemas import MatchResponse


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
def test_document_summary_defaults() -> None:
    """DocumentSummary accepts vendor_name and document_number, defaulting to None."""
    doc_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    summary = DocumentSummary(
        id=doc_id,
        doc_type="quote",
        status="confirmed",
        pages=2,
        size_bytes=1024,
        created_at=now,
        duplicate_of=None,
        suspicious=False,
    )
    assert summary.vendor_name is None
    assert summary.document_number is None

    summary_with_titles = DocumentSummary(
        id=doc_id,
        doc_type="quote",
        status="confirmed",
        pages=2,
        size_bytes=1024,
        created_at=now,
        duplicate_of=None,
        suspicious=False,
        vendor_name="Gulf Line IT Trading",
        document_number="Q-1042",
    )
    assert summary_with_titles.vendor_name == "Gulf Line IT Trading"
    assert summary_with_titles.document_number == "Q-1042"


@pytest.mark.unit
def test_list_documents_populates_vendor_and_doc_number() -> None:
    """list_documents returns vendor_name (linked vendor or extraction) and document_number."""
    doc_id_1 = uuid.uuid4()
    doc_id_2 = uuid.uuid4()
    vendor_id = uuid.uuid4()
    ext_id_1 = uuid.uuid4()
    ext_id_2 = uuid.uuid4()

    mock_doc1 = MagicMock()
    mock_doc1.id = doc_id_1
    mock_doc1.vendor_id = vendor_id
    mock_doc1.doc_type = "quote"
    mock_doc1.status = "confirmed"
    mock_doc1.pages = 1
    mock_doc1.size_bytes = 2048
    mock_doc1.created_at = datetime.now(timezone.utc)
    mock_doc1.duplicate_of = None
    mock_doc1.suspicious = False
    mock_doc1.pr_id = None

    mock_doc2 = MagicMock()
    mock_doc2.id = doc_id_2
    mock_doc2.vendor_id = None
    mock_doc2.doc_type = "invoice"
    mock_doc2.status = "ready"
    mock_doc2.pages = 1
    mock_doc2.size_bytes = 4096
    mock_doc2.created_at = datetime.now(timezone.utc)
    mock_doc2.duplicate_of = None
    mock_doc2.suspicious = False
    mock_doc2.pr_id = None

    mock_db = MagicMock()

    # db.execute for:
    # 1. select(Document) -> [mock_doc1, mock_doc2]
    # 2. select(Vendor) -> [(vendor_id, "Gulf Line IT Trading")]
    # 3. select(Extraction) -> [(ext_id_1, doc_id_1), (ext_id_2, doc_id_2)]
    # 4. select(ExtractedField) ->
    #    [(ext_id_1, "document_number", "Q-1042"),
    #     (ext_id_2, "vendor_name", "Falcon Supplies"),
    #     (ext_id_2, "po_number", "PO-9901")]
    res_docs = MagicMock()
    res_docs.scalars.return_value.all.return_value = [mock_doc1, mock_doc2]

    res_vendors = MagicMock()
    res_vendors.all.return_value = [(vendor_id, "Gulf Line IT Trading")]

    res_exts = MagicMock()
    res_exts.all.return_value = [(ext_id_1, doc_id_1), (ext_id_2, doc_id_2)]

    res_fields = MagicMock()
    res_fields.all.return_value = [
        (ext_id_1, "document_number", "Q-1042"),
        (ext_id_2, "vendor_name", "Falcon Supplies"),
        (ext_id_2, "po_number", "PO-9901"),
    ]

    mock_db.execute.side_effect = [res_docs, res_vendors, res_exts, res_fields]

    principal = _make_principal(["buyer"])
    results = list_documents(db=mock_db, principal=principal, limit=50, offset=0)

    assert len(results) == 2
    # doc1: linked vendor name, document_number
    assert results[0].id == doc_id_1
    assert results[0].vendor_name == "Gulf Line IT Trading"
    assert results[0].document_number == "Q-1042"

    # doc2: vendor_name from extraction, po_number fallback for document_number
    assert results[1].id == doc_id_2
    assert results[1].vendor_name == "Falcon Supplies"
    assert results[1].document_number == "PO-9901"


@pytest.mark.unit
def test_list_documents_null_values_are_not_errors() -> None:
    """Documents with no linked vendor and no extractions return null values without error."""
    doc_id = uuid.uuid4()
    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.vendor_id = None
    mock_doc.doc_type = "other"
    mock_doc.status = "queued"
    mock_doc.pages = 1
    mock_doc.size_bytes = 1000
    mock_doc.created_at = datetime.now(timezone.utc)
    mock_doc.duplicate_of = None
    mock_doc.suspicious = False
    mock_doc.pr_id = None

    mock_db = MagicMock()
    res_docs = MagicMock()
    res_docs.scalars.return_value.all.return_value = [mock_doc]

    res_exts = MagicMock()
    res_exts.all.return_value = []

    # vendor_id is None, so vendor query is skipped; then extraction query runs
    mock_db.execute.side_effect = [res_docs, res_exts]

    principal = _make_principal(["buyer"])
    results = list_documents(db=mock_db, principal=principal, limit=50, offset=0)

    assert len(results) == 1
    assert results[0].id == doc_id
    assert results[0].vendor_name is None
    assert results[0].document_number is None


@pytest.mark.unit
def test_match_response_fields() -> None:
    """MatchResponse supports optional invoice_document_number and vendor_name."""
    now = datetime.now(timezone.utc)
    res = MatchResponse(
        id=uuid.uuid4(),
        invoice_document_id=uuid.uuid4(),
        po_id=uuid.uuid4(),
        run_by=uuid.uuid4(),
        overall_status="matched",
        created_at=now,
        invoice_document_number="INV-2291",
        vendor_name="Gulf Line IT Trading",
    )
    assert res.invoice_document_number == "INV-2291"
    assert res.vendor_name == "Gulf Line IT Trading"
