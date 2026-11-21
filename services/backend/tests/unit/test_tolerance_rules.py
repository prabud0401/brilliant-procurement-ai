import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.core.models import ExtractedLine, MatchLine, POLine
from app.core.policy import Principal
from app.matching.engine import execute_three_way_match
from app.matching.schemas import MatchLineResponse
from app.matching.service import list_exceptions


@pytest.mark.unit
def test_matching_s1_perfect_match() -> None:
    po_id = uuid.uuid4()
    po_line = POLine(
        id=uuid.uuid4(),
        po_id=po_id,
        line_no=1,
        description="Office Desks",
        qty=Decimal("10.00"),
        uom="unit",
        unit_price=Decimal("500.00"),
        vat_rate=Decimal("0.05"),
    )

    inv_line = ExtractedLine(
        id=uuid.uuid4(),
        extraction_id=uuid.uuid4(),
        line_no=1,
        item_code="DSK-01",
        description="Office Desks",
        qty=Decimal("10.00"),
        uom="unit",
        unit_price=Decimal("500.00"),
        line_total=Decimal("5000.00"),
    )

    dn_lines_by_po_line = {po_line.id: [Decimal("10.00")]}
    invoice_vat = Decimal("250.00")
    tolerances = {
        "invoiced_vs_received_qty_max_units": 0,
        "received_vs_ordered_qty_max_pct": 0.0,
        "unit_price_variance_pct": 2.0,
        "unit_price_variance_max_aed": "50.00",
        "vat_max_difference_aed": "1.00",
    }

    result = execute_three_way_match(
        po_lines=[po_line],
        invoice_lines=[inv_line],
        dn_lines_by_po_line=dn_lines_by_po_line,
        invoice_vat=invoice_vat,
        tolerances=tolerances,
    )

    assert result["overall_status"] == "matched"
    assert len(result["exceptions"]) == 0
    assert result["lines"][0]["status"] == "matched"


@pytest.mark.unit
def test_acceptance_s3_quantity_variance_exception() -> None:
    # S3: PO 10, DN 10, invoice 12 -> gives quantity exception
    po_id = uuid.uuid4()
    po_line = POLine(
        id=uuid.uuid4(),
        po_id=po_id,
        line_no=1,
        description="Office Desks",
        qty=Decimal("10.00"),
        uom="unit",
        unit_price=Decimal("500.00"),
        vat_rate=Decimal("0.05"),
    )

    inv_line = ExtractedLine(
        id=uuid.uuid4(),
        extraction_id=uuid.uuid4(),
        line_no=1,
        item_code="DSK-01",
        description="Office Desks",
        qty=Decimal("12.00"),  # Over-billed: 12 units
        uom="unit",
        unit_price=Decimal("500.00"),
        line_total=Decimal("6000.00"),
    )

    dn_lines_by_po_line = {po_line.id: [Decimal("10.00")]}
    invoice_vat = Decimal("300.00")
    tolerances = {
        "invoiced_vs_received_qty_max_units": 0,
        "received_vs_ordered_qty_max_pct": 0.0,
        "unit_price_variance_pct": 2.0,
        "unit_price_variance_max_aed": "50.00",
        "vat_max_difference_aed": "1.00",
    }

    result = execute_three_way_match(
        po_lines=[po_line],
        invoice_lines=[inv_line],
        dn_lines_by_po_line=dn_lines_by_po_line,
        invoice_vat=invoice_vat,
        tolerances=tolerances,
    )

    assert result["overall_status"] == "exception"
    assert len(result["exceptions"]) >= 1

    qty_ex = [e for e in result["exceptions"] if e["kind"] == "qty_variance"]
    assert len(qty_ex) == 1
    assert "invoiced 12" in qty_ex[0]["reason"]
    assert "received 10" in qty_ex[0]["reason"]
    assert qty_ex[0]["amount_impact_aed"] == Decimal("1000.00")


@pytest.mark.unit
def test_price_variance_tolerance_within_and_exceeding() -> None:
    po_id = uuid.uuid4()
    po_line = POLine(
        id=uuid.uuid4(),
        po_id=po_id,
        line_no=1,
        description="Laptops",
        qty=Decimal("1.00"),
        uom="unit",
        unit_price=Decimal("1000.00"),
        vat_rate=Decimal("0.05"),
    )

    # 1. Within tolerance: +1% = 1010 AED (allowed is 2% = 20 AED)
    inv_line_within = ExtractedLine(
        id=uuid.uuid4(),
        extraction_id=uuid.uuid4(),
        line_no=1,
        description="Laptops",
        qty=Decimal("1.00"),
        uom="unit",
        unit_price=Decimal("1010.00"),
        line_total=Decimal("1010.00"),
    )

    dn_lines = {po_line.id: [Decimal("1.00")]}
    tolerances = {
        "invoiced_vs_received_qty_max_units": 0,
        "unit_price_variance_pct": 2.0,
        "unit_price_variance_max_aed": "50.00",
        "vat_max_difference_aed": "1.00",
    }

    res_within = execute_three_way_match(
        po_lines=[po_line],
        invoice_lines=[inv_line_within],
        dn_lines_by_po_line=dn_lines,
        invoice_vat=Decimal("50.50"),
        tolerances=tolerances,
    )
    assert res_within["overall_status"] == "within_tolerance"
    assert len(res_within["exceptions"]) == 0

    # 2. Exceeding tolerance: +10% = 1100 AED (variance 100 AED > cap 50 AED)
    inv_line_exceed = ExtractedLine(
        id=uuid.uuid4(),
        extraction_id=uuid.uuid4(),
        line_no=1,
        description="Laptops",
        qty=Decimal("1.00"),
        uom="unit",
        unit_price=Decimal("1100.00"),
        line_total=Decimal("1100.00"),
    )

    res_exceed = execute_three_way_match(
        po_lines=[po_line],
        invoice_lines=[inv_line_exceed],
        dn_lines_by_po_line=dn_lines,
        invoice_vat=Decimal("55.00"),
        tolerances=tolerances,
    )
    assert res_exceed["overall_status"] == "exception"
    price_ex = [e for e in res_exceed["exceptions"] if e["kind"] == "price_variance"]
    assert len(price_ex) == 1
    assert price_ex[0]["amount_impact_aed"] == Decimal("100.00")


@pytest.mark.unit
def test_match_line_description_and_line_no_mapping() -> None:
    # 1. Populated from PO line when po_line is present
    po_line = POLine(
        id=uuid.uuid4(),
        po_id=uuid.uuid4(),
        line_no=3,
        description="Ergonomic Chairs",
        qty=Decimal("5.00"),
        uom="unit",
        unit_price=Decimal("400.00"),
        vat_rate=Decimal("0.05"),
    )
    inv_line = ExtractedLine(
        id=uuid.uuid4(),
        extraction_id=uuid.uuid4(),
        line_no=1,
        description="Chairs - Invoice description",
        qty=Decimal("5.00"),
        unit_price=Decimal("400.00"),
    )

    ml = MatchLine(
        id=uuid.uuid4(),
        match_id=uuid.uuid4(),
        po_line_id=po_line.id,
        invoice_line_id=inv_line.id,
        ordered_qty=Decimal("5.00"),
        received_qty=Decimal("5.00"),
        invoiced_qty=Decimal("5.00"),
        po_unit_price=Decimal("400.00"),
        inv_unit_price=Decimal("400.00"),
        variance_aed=Decimal("0.00"),
        status="matched",
    )
    ml.po_line = po_line
    ml.invoice_line = inv_line

    assert ml.description == "Ergonomic Chairs"
    assert ml.line_no == 3

    resp = MatchLineResponse.model_validate(ml)
    assert resp.description == "Ergonomic Chairs"
    assert resp.line_no == 3
    assert resp.inv_unit_price == Decimal("400.00")

    # 2. Fallback to invoice line when po_line is absent
    ml_unmatched = MatchLine(
        id=uuid.uuid4(),
        match_id=uuid.uuid4(),
        po_line_id=None,
        invoice_line_id=inv_line.id,
        invoiced_qty=Decimal("5.00"),
        inv_unit_price=Decimal("400.00"),
        variance_aed=Decimal("0.00"),
        status="exception",
    )
    ml_unmatched.po_line = None
    ml_unmatched.invoice_line = inv_line

    assert ml_unmatched.description == "Chairs - Invoice description"
    assert ml_unmatched.line_no == 1

    resp_unmatched = MatchLineResponse.model_validate(ml_unmatched)
    assert resp_unmatched.description == "Chairs - Invoice description"
    assert resp_unmatched.line_no == 1
    assert resp_unmatched.inv_unit_price == Decimal("400.00")


@pytest.mark.unit
def test_list_exceptions_unresolved_filter() -> None:
    # Verify that status_filter="unresolved" applies IN ('open', 'escalated')
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query

    principal = Principal(
        id=uuid.uuid4(),
        email="buyer@example.com",
        display_name="Test Buyer",
        roles=["buyer"],
        department_id=None,
        department_name=None,
        approval_limit_aed=Decimal("10000.00"),
    )

    # Call with unresolved
    list_exceptions(mock_db, principal, status_filter="unresolved")

    # Verify query.filter was called with an IN clause on MatchException.status
    assert mock_query.filter.called
    filter_call = mock_query.filter.call_args[0][0]
    # Check string representation or SQL expression of the binary expression
    filter_sql = str(filter_call)
    assert "open" in filter_sql or "status" in filter_sql

    # Also verify "needs_action" synonym
    mock_query.filter.reset_mock()
    list_exceptions(mock_db, principal, status_filter="needs_action")
    assert mock_query.filter.called
