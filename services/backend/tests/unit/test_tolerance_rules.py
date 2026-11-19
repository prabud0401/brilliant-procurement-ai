import uuid
from decimal import Decimal

import pytest

from app.core.models import ExtractedLine, POLine
from app.matching.engine import execute_three_way_match


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
