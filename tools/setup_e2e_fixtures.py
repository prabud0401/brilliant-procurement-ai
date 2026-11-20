"""Fixture helpers for E2E tests (S1, S3, S4).

Allows Playwright tests to quickly set up confirmed quotations, delivery notes,
and invoices as instructed by R09 prompt.
"""

from __future__ import annotations

import sys
import uuid
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.models import (
    Department,
    Document,
    ExtractedField,
    ExtractedLine,
    Extraction,
    POLine,
    PurchaseOrder,
    User,
    Vendor,
)
from app.core.policy import Principal
from app.matching.service import create_match


def get_principal_for_user(user: User) -> Principal:
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
    )


def setup_s1_quotes(pr_id_str: str) -> list[str]:
    """Link 3 confirmed S1 quotation documents to the given PR ID."""
    db: Session = SessionLocal()
    try:
        pr_id = uuid.UUID(pr_id_str)
        buyer = db.query(User).filter(User.email == "buyer1@demo-holdings.example").one()
        it_dept = db.query(Department).filter(Department.name == "IT").one()

        # Check or fetch vendors
        vendor_gulf = db.query(Vendor).filter(Vendor.name.ilike("%Gulf Line%")).first()
        if not vendor_gulf:
            vendor_gulf = Vendor(
                name="Gulf Line IT Trading LLC",
                trn="100123456789003",
                payment_terms_days=30,
                created_by=buyer.id,
            )
            db.add(vendor_gulf)
            db.flush()

        vendor_falcon = db.query(Vendor).filter(Vendor.name.ilike("%Falcon%")).first()
        if not vendor_falcon:
            vendor_falcon = Vendor(
                name="Falcon Office Systems LLC",
                trn="100987654321003",
                payment_terms_days=30,
                created_by=buyer.id,
            )
            db.add(vendor_falcon)
            db.flush()

        vendor_corniche = db.query(Vendor).filter(Vendor.name.ilike("%Corniche%")).first()
        if not vendor_corniche:
            vendor_corniche = Vendor(
                name="Corniche Digital Supplies LLC",
                trn="100555444333003",
                payment_terms_days=60,
                created_by=buyer.id,
            )
            db.add(vendor_corniche)
            db.flush()

        quotes_data = [
            {
                "vendor": vendor_gulf,
                "total": "27500.00",
                "lead_time": "3",
                "payment_terms": "30",
                "trn": vendor_gulf.trn,
                "lines": [
                    {
                        "code": "IT-LAP-14",
                        "desc": "Laptop 14in Intel Core i7 16GB RAM 512GB SSD",
                        "qty": Decimal("10.00"),
                        "price": Decimal("1900.00"),
                        "total": Decimal("19000.00"),
                    },
                    {
                        "code": "IT-MON-27",
                        "desc": "Monitor 27in QHD IPS USB-C 75Hz",
                        "qty": Decimal("10.00"),
                        "price": Decimal("850.00"),
                        "total": Decimal("8500.00"),
                    },
                ],
            },
            {
                "vendor": vendor_falcon,
                "total": "28500.00",
                "lead_time": "5",
                "payment_terms": "30",
                "trn": vendor_falcon.trn,
                "lines": [
                    {
                        "code": "IT-LAP-14",
                        "desc": "Laptop 14in Intel Core i7 16GB RAM 512GB SSD",
                        "qty": Decimal("10.00"),
                        "price": Decimal("1980.00"),
                        "total": Decimal("19800.00"),
                    },
                    {
                        "code": "IT-MON-27",
                        "desc": "Monitor 27in QHD IPS USB-C 75Hz",
                        "qty": Decimal("10.00"),
                        "price": Decimal("870.00"),
                        "total": Decimal("8700.00"),
                    },
                ],
            },
            {
                "vendor": vendor_corniche,
                "total": "29900.00",
                "lead_time": "7",
                "payment_terms": "60",
                "trn": vendor_corniche.trn,
                "lines": [
                    {
                        "code": "IT-LAP-14",
                        "desc": "Laptop 14in Intel Core i7 16GB RAM 512GB SSD",
                        "qty": Decimal("10.00"),
                        "price": Decimal("2050.00"),
                        "total": Decimal("20500.00"),
                    },
                    {
                        "code": "IT-MON-27",
                        "desc": "Monitor 27in QHD IPS USB-C 75Hz",
                        "qty": Decimal("10.00"),
                        "price": Decimal("940.00"),
                        "total": Decimal("9400.00"),
                    },
                ],
            },
        ]

        doc_ids: list[str] = []
        for q in quotes_data:
            doc = Document(
                owner_id=buyer.id,
                department_id=it_dept.id,
                pr_id=pr_id,
                vendor_id=q["vendor"].id,
                doc_type="quote",
                status="confirmed",
                file_sha256=uuid.uuid4().hex,
                blob_path=f"e2e/{uuid.uuid4()}.pdf",
                mime="application/pdf",
                size_bytes=1024,
            )
            db.add(doc)
            db.flush()
            doc_ids.append(str(doc.id))

            ext = Extraction(document_id=doc.id, status="completed")
            db.add(ext)
            db.flush()

            db.add_all(
                [
                    ExtractedField(
                        extraction_id=ext.id,
                        name="total",
                        value_raw=str(q["total"]),
                        status="confirmed",
                    ),
                    ExtractedField(
                        extraction_id=ext.id,
                        name="lead_time_days",
                        value_raw=str(q["lead_time"]),
                        status="confirmed",
                    ),
                    ExtractedField(
                        extraction_id=ext.id,
                        name="payment_terms_days",
                        value_raw=str(q["payment_terms"]),
                        status="confirmed",
                    ),
                    ExtractedField(
                        extraction_id=ext.id,
                        name="currency",
                        value_raw="AED",
                        status="confirmed",
                    ),
                    ExtractedField(
                        extraction_id=ext.id,
                        name="trn",
                        value_raw=str(q["trn"]),
                        status="confirmed",
                    ),
                ]
            )

            for idx, line in enumerate(q["lines"], start=1):
                db.add(
                    ExtractedLine(
                        extraction_id=ext.id,
                        line_no=idx,
                        item_code=str(line["code"]),
                        description=str(line["desc"]),
                        qty=line["qty"],
                        unit_price=line["price"],
                        line_total=line["total"],
                        status="confirmed",
                    )
                )

        db.commit()
        return doc_ids
    finally:
        db.close()


def setup_s3_match() -> tuple[str, str]:
    """Create S3 PO, DN (10 units), Invoice (12 units) and run match.

    Returns (match_id, exception_id).
    """
    db: Session = SessionLocal()
    try:
        buyer = db.query(User).filter(User.email == "buyer1@demo-holdings.example").one()
        it_dept = db.query(Department).filter(Department.name == "IT").one()
        vendor = db.query(Vendor).first()
        assert vendor is not None

        # 1. Create S3 Purchase Order
        po = PurchaseOrder(
            number=f"PO-S3-{uuid.uuid4().hex[:6].upper()}",
            vendor_id=vendor.id,
            department_id=it_dept.id,
            created_by=buyer.id,
            subtotal=Decimal("5000.00"),
            vat=Decimal("250.00"),
            total=Decimal("5250.00"),
            status="approved",
        )
        db.add(po)
        db.flush()

        po_line = POLine(
            po_id=po.id,
            line_no=1,
            description="High-Speed Network Switches 48-Port",
            qty=Decimal("10.00"),
            uom="EA",
            unit_price=Decimal("500.00"),
            vat_rate=Decimal("0.05"),
        )
        db.add(po_line)
        db.flush()

        # 2. Create S3 Delivery Note (10 units received)
        dn_doc = Document(
            owner_id=buyer.id,
            department_id=it_dept.id,
            po_id=po.id,
            vendor_id=vendor.id,
            doc_type="delivery_note",
            status="confirmed",
            file_sha256=uuid.uuid4().hex,
            blob_path=f"e2e/{uuid.uuid4()}.pdf",
            mime="application/pdf",
            size_bytes=1024,
        )
        db.add(dn_doc)
        db.flush()

        dn_ext = Extraction(document_id=dn_doc.id, status="completed")
        db.add(dn_ext)
        db.flush()

        db.add_all(
            [
                ExtractedField(
                    extraction_id=dn_ext.id,
                    name="po_number",
                    value_raw=po.number,
                    status="confirmed",
                ),
                ExtractedLine(
                    extraction_id=dn_ext.id,
                    line_no=1,
                    description="High-Speed Network Switches 48-Port",
                    qty=Decimal("10.00"),
                    status="confirmed",
                ),
            ]
        )
        db.flush()

        # 3. Create S3 Invoice (12 units invoiced vs 10 received)
        inv_doc = Document(
            owner_id=buyer.id,
            department_id=it_dept.id,
            po_id=po.id,
            vendor_id=vendor.id,
            doc_type="invoice",
            status="confirmed",
            file_sha256=uuid.uuid4().hex,
            blob_path=f"e2e/{uuid.uuid4()}.pdf",
            mime="application/pdf",
            size_bytes=1024,
        )
        db.add(inv_doc)
        db.flush()

        inv_ext = Extraction(document_id=inv_doc.id, status="completed")
        db.add(inv_ext)
        db.flush()

        db.add_all(
            [
                ExtractedField(
                    extraction_id=inv_ext.id,
                    name="po_number",
                    value_raw=po.number,
                    status="confirmed",
                ),
                ExtractedField(
                    extraction_id=inv_ext.id,
                    name="total",
                    value_raw="6300.00",
                    status="confirmed",
                ),
                ExtractedField(
                    extraction_id=inv_ext.id,
                    name="vat_amount",
                    value_raw="300.00",
                    status="confirmed",
                ),
                ExtractedLine(
                    extraction_id=inv_ext.id,
                    line_no=1,
                    description="High-Speed Network Switches 48-Port",
                    qty=Decimal("12.00"),  # Over-billing!
                    unit_price=Decimal("500.00"),
                    line_total=Decimal("6000.00"),
                    status="confirmed",
                ),
            ]
        )
        db.commit()

        # 4. Run match via matching service
        buyer_principal = get_principal_for_user(buyer)
        match_resp = create_match(db, inv_doc.id, buyer_principal)
        match_id = str(match_resp.id)
        assert len(match_resp.exceptions) > 0, "No exceptions created for S3 match"
        exc_id = str(match_resp.exceptions[0].id)
        return match_id, exc_id
    finally:
        db.close()


def clean_e2e_documents() -> None:
    """Clear test documents, PRs, POs, matches, and comparisons for idempotent E2E."""
    db: Session = SessionLocal()
    try:
        db.execute(text("DELETE FROM match_exceptions"))
        db.execute(text("DELETE FROM match_lines"))
        db.execute(text("DELETE FROM matches"))
        db.execute(text("DELETE FROM approval_steps"))
        db.execute(text("DELETE FROM comparison_pairings"))
        db.execute(text("DELETE FROM comparison_quotes"))
        db.execute(text("DELETE FROM comparisons"))
        db.execute(text("DELETE FROM po_lines"))
        db.execute(text("DELETE FROM purchase_orders"))
        db.execute(text("DELETE FROM pr_lines"))
        db.execute(text("DELETE FROM purchase_requests"))
        db.execute(text("DELETE FROM extracted_lines"))
        db.execute(text("DELETE FROM extracted_fields"))
        db.execute(text("DELETE FROM extractions"))
        db.execute(text("DELETE FROM documents"))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "clean-e2e":
        clean_e2e_documents()
        print("CLEANED")
    elif action == "link-s1-quotes":
        pr_id = sys.argv[2]
        ids = setup_s1_quotes(pr_id)
        print(",".join(ids))
    elif action == "setup-s3-match":
        m_id, e_id = setup_s3_match()
        print(f"{m_id}:{e_id}")
    else:
        print("Unknown action")
        sys.exit(1)
