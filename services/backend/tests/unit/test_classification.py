"""Unit tests for auto-classification of untyped procurement documents (F04)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.ai.providers.mock import MockLlmClient
from app.ai.providers.replay import ReplayLlmClient
from app.ai.schemas import ExtractionResult, OCRPage, OCRResult, OCRWord
from app.core.errors import ProblemException
from app.core.models import Document
from app.extraction.service import run_extraction


@pytest.mark.unit
def test_mock_and_replay_classify_defaults_to_other_and_matches_keywords() -> None:
    """Mock and replay classify must return 'other' when no keyword matches,

    and recognise tax invoice, purchase order/PO, delivery note/DN, quotation/quote.
    """
    for client in (MockLlmClient(), ReplayLlmClient()):
        # 1. Tax invoice
        assert client.classify("TAX INVOICE\nInvoice #: INV-100\nTotal: 500 AED") == "invoice"
        assert client.classify("Standard Invoice No 504") == "invoice"

        # 2. Purchase order / PO
        assert client.classify("PURCHASE ORDER\nPO Number: PO-0042") == "purchase_order"
        assert client.classify("Vendor: Acme\nPO: 99421\nAmount: 100") == "purchase_order"

        # 3. Delivery note / DN
        assert client.classify("DELIVERY NOTE\nReceipt of items") == "delivery_note"
        assert client.classify("DN-771 Delivered by driver") == "delivery_note"

        # 4. Quotation / Quote
        assert client.classify("QUOTATION\nPrice proposal valid 30 days") == "quote"
        assert client.classify("Supplier Quote Q-1042") == "quote"

        # 5. Default is 'other' (not 'quote')
        assert client.classify("Company Annual Report 2026") == "other"
        assert client.classify("Employee Contract Agreement") == "other"
        assert client.classify("Meeting minutes and agenda") == "other"
        assert client.classify("") == "other"

        # Verify classify_with_usage returns metadata and populates last_usage
        label, meta = client.classify_with_usage("QUOTATION\nPrice proposal")
        assert label == "quote"
        assert meta["tokens_in"] > 0
        assert meta["tokens_out"] > 0
        assert client.last_usage == meta


def _make_dummy_ocr() -> OCRResult:
    word1 = OCRWord(content="TAX", polygon=[], confidence=0.99)
    word2 = OCRWord(content="INVOICE", polygon=[], confidence=0.99)
    page = OCRPage(page_number=1, words=[word1, word2], lines=[])
    return OCRResult(content="TAX INVOICE #999", pages=[page], documents=[], tables=[])


@pytest.mark.unit
def test_classification_runs_only_when_type_is_none_or_other() -> None:
    """Auto-classification must run only when document.doc_type is None or 'other'.

    Explicit types (quote, invoice, purchase_order, delivery_note) must never be re-classified.
    """
    for initial_type, should_classify in [
        ("other", True),
        (None, True),
        ("quote", False),
        ("invoice", False),
        ("purchase_order", False),
        ("delivery_note", False),
    ]:
        doc_id = uuid.uuid4()
        dummy_doc = Document(
            id=doc_id,
            owner_id=uuid.uuid4(),
            department_id=uuid.uuid4(),
            doc_type=initial_type,  # type: ignore[arg-type]
            status="queued",
            file_sha256="test-sha",
            blob_path="test.pdf",
            mime="application/pdf",
            pages=1,
            size_bytes=500,
            source="upload",
        )

        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = dummy_doc
        mock_session.execute.return_value.scalar_one.return_value = 0

        mock_storage = MagicMock()
        mock_storage.download.return_value = b"%PDF-dummy"

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = _make_dummy_ocr()

        mock_llm = MagicMock()
        mock_llm.classify_with_usage.return_value = ("invoice", {"tokens_in": 60, "tokens_out": 15})
        mock_llm.extract.return_value = (
            ExtractionResult(doc_type=dummy_doc.doc_type or "other", header={}, lines=[]),
            {"tokens_in": 500, "tokens_out": 200, "model": "mock-llm"},
        )

        with (
            patch("app.extraction.service.get_storage", return_value=mock_storage),
            patch("app.extraction.service.get_document_analyzer", return_value=mock_analyzer),
            patch("app.extraction.service.get_llm_client", return_value=mock_llm),
            patch("app.extraction.service.check_daily_budget"),
            patch("app.extraction.service.record_audit"),
            patch("app.extraction.service.get_cached_extraction", return_value=None),
            patch("app.extraction.service.store_cached_extraction"),
        ):
            run_extraction(mock_session, doc_id)

            if should_classify:
                mock_llm.classify_with_usage.assert_called_once()
                assert dummy_doc.doc_type == "invoice"
            else:
                mock_llm.classify_with_usage.assert_not_called()
                assert dummy_doc.doc_type == initial_type


@pytest.mark.unit
def test_each_label_maps_and_audit_entry_recorded() -> None:
    """Each classified label (quote, purchase_order, delivery_note, invoice) maps correctly

    and writes an audit entry with action='document.classified', before/after doc_type,
    and no document text.
    """
    labels = ["quote", "purchase_order", "delivery_note", "invoice"]
    for label in labels:
        doc_id = uuid.uuid4()
        dummy_doc = Document(
            id=doc_id,
            owner_id=uuid.uuid4(),
            department_id=uuid.uuid4(),
            doc_type="other",
            status="queued",
            file_sha256=f"test-sha-{label}",
            blob_path="test.pdf",
            mime="application/pdf",
            pages=1,
            size_bytes=500,
            source="upload",
        )

        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = dummy_doc
        mock_session.execute.return_value.scalar_one.return_value = 0

        mock_storage = MagicMock()
        mock_storage.download.return_value = b"%PDF-dummy"

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = _make_dummy_ocr()

        mock_llm = MagicMock()
        mock_llm.classify_with_usage.return_value = (label, {"tokens_in": 40, "tokens_out": 10})
        mock_llm.extract.return_value = (
            ExtractionResult(doc_type=label, header={}, lines=[]),
            {"tokens_in": 400, "tokens_out": 150, "model": "mock-llm"},
        )

        audit_calls: list[dict[str, object]] = []

        def fake_record_audit(**kwargs: object) -> None:
            audit_calls.append(kwargs)

        with (
            patch("app.extraction.service.get_storage", return_value=mock_storage),
            patch("app.extraction.service.get_document_analyzer", return_value=mock_analyzer),
            patch("app.extraction.service.get_llm_client", return_value=mock_llm),
            patch("app.extraction.service.check_daily_budget"),
            patch("app.extraction.service.record_audit", side_effect=fake_record_audit),
            patch("app.extraction.service.get_cached_extraction", return_value=None),
            patch("app.extraction.service.store_cached_extraction"),
        ):
            run_extraction(mock_session, doc_id)

            assert dummy_doc.doc_type == label
            # Verify extract was passed the classified doc_type
            mock_llm.extract.assert_called_once()
            _, ext_kwargs = mock_llm.extract.call_args
            assert ext_kwargs["doc_type"] == label

            # Check audit entry for document.classified
            classified_audit = next(
                (c for c in audit_calls if c.get("action") == "document.classified"),
                None,
            )
            assert classified_audit is not None
            assert classified_audit["entity_type"] == "document"
            assert classified_audit["entity_id"] == doc_id
            assert classified_audit["before"] == {"doc_type": "other"}
            assert classified_audit["after"] == {"doc_type": label}
            # Verify no document text was stored in audit
            assert "text" not in str(classified_audit)
            assert "content" not in str(classified_audit)


@pytest.mark.unit
def test_unknown_or_exception_keeps_other_and_extraction_completes() -> None:
    """When classify returns 'other' or raises an exception, document remains 'other'

    and extraction continues to completion without failing.
    """
    for failure_mode in ["other", "exception", "problem_exception", "empty"]:
        doc_id = uuid.uuid4()
        dummy_doc = Document(
            id=doc_id,
            owner_id=uuid.uuid4(),
            department_id=uuid.uuid4(),
            doc_type="other",
            status="queued",
            file_sha256=f"test-sha-{failure_mode}",
            blob_path="test.pdf",
            mime="application/pdf",
            pages=1,
            size_bytes=500,
            source="upload",
        )

        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = dummy_doc
        mock_session.execute.return_value.scalar_one.return_value = 0

        mock_storage = MagicMock()
        mock_storage.download.return_value = b"%PDF-dummy"

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = _make_dummy_ocr()

        mock_llm = MagicMock()
        if failure_mode == "other":
            mock_llm.classify_with_usage.return_value = (
                "other",
                {"tokens_in": 50, "tokens_out": 5},
            )
        elif failure_mode == "empty":
            mock_llm.classify_with_usage.return_value = ("", {"tokens_in": 50, "tokens_out": 5})
        elif failure_mode == "problem_exception":
            mock_llm.classify_with_usage.side_effect = ProblemException(
                status_code=502, code="AI_RESPONSE_TRUNCATED", title="Truncated"
            )
        else:
            mock_llm.classify_with_usage.side_effect = RuntimeError("Network timeout")

        mock_llm.extract.return_value = (
            ExtractionResult(doc_type="other", header={}, lines=[]),
            {"tokens_in": 300, "tokens_out": 100, "model": "mock-llm"},
        )

        with (
            patch("app.extraction.service.get_storage", return_value=mock_storage),
            patch("app.extraction.service.get_document_analyzer", return_value=mock_analyzer),
            patch("app.extraction.service.get_llm_client", return_value=mock_llm),
            patch("app.extraction.service.check_daily_budget"),
            patch("app.extraction.service.record_audit"),
            patch("app.extraction.service.get_cached_extraction", return_value=None),
            patch("app.extraction.service.store_cached_extraction"),
        ):
            extraction = run_extraction(mock_session, doc_id)
            assert extraction is not None
            assert dummy_doc.doc_type == "other"
            assert dummy_doc.status == "needs_review"
            mock_llm.extract.assert_called_once()


@pytest.mark.unit
def test_classify_cost_and_tokens_are_metered() -> None:
    """Classification tokens must be added to extraction tokens and cost."""
    doc_id = uuid.uuid4()
    dummy_doc = Document(
        id=doc_id,
        owner_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        doc_type="other",
        status="queued",
        file_sha256="test-sha-metered",
        blob_path="test.pdf",
        mime="application/pdf",
        pages=1,
        size_bytes=500,
        source="upload",
    )

    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = dummy_doc
    mock_session.execute.return_value.scalar_one.return_value = 0

    mock_storage = MagicMock()
    mock_storage.download.return_value = b"%PDF-dummy"

    mock_analyzer = MagicMock()
    mock_analyzer.analyze.return_value = _make_dummy_ocr()

    mock_llm = MagicMock()
    cls_tokens_in, cls_tokens_out = 150, 25
    ext_tokens_in, ext_tokens_out = 800, 200
    mock_llm.classify_with_usage.return_value = (
        "invoice",
        {"tokens_in": cls_tokens_in, "tokens_out": cls_tokens_out},
    )
    mock_llm.extract.return_value = (
        ExtractionResult(doc_type="invoice", header={}, lines=[]),
        {"tokens_in": ext_tokens_in, "tokens_out": ext_tokens_out, "model": "mock-llm"},
    )

    added_objects: list[object] = []
    mock_session.add.side_effect = added_objects.append

    with (
        patch("app.extraction.service.get_storage", return_value=mock_storage),
        patch("app.extraction.service.get_document_analyzer", return_value=mock_analyzer),
        patch("app.extraction.service.get_llm_client", return_value=mock_llm),
        patch("app.extraction.service.check_daily_budget"),
        patch("app.extraction.service.record_audit"),
        patch("app.extraction.service.get_cached_extraction", return_value=None),
        patch("app.extraction.service.store_cached_extraction"),
    ):
        extraction = run_extraction(mock_session, doc_id)
        # Check extraction tokens include classification
        assert extraction.tokens_in == ext_tokens_in + cls_tokens_in
        assert extraction.tokens_out == ext_tokens_out + cls_tokens_out
        assert extraction.est_cost > Decimal("0.0000")
        assert extraction.di_model == "prebuilt-layout"
