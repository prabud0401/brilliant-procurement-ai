"""ReportLab layouts and canvas painters with distinct styles for vendors."""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image as PlatypusImage,
)
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from tools.datagen.models import ScenarioDocSpec
from tools.datagen.scanner import create_scanned_image


class SyntheticDocCanvas(canvas.Canvas):  # type: ignore[misc]
    """Custom ReportLab canvas that guarantees footer placement and determinism."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["invariant"] = True
        super().__init__(*args, **kwargs)
        self.pages: list[Any] = []
        self.hidden_injections: list[str] = []

    def showPage(self) -> None:
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, total_pages: int) -> None:
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Footer banner line
        width, _ = self._pagesize
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.75)
        self.line(40, 36, width - 40, 36)

        # Primary required footer text
        self.drawCentredString(width / 2.0, 22, "SAMPLE – SYNTHETIC DATA")
        self.drawRightString(width - 40, 22, f"Page {self._pageNumber} of {total_pages}")
        self.drawString(40, 22, "Demo Holdings LLC • Synthetic Test Dataset")

        # Hidden text injection layer (for S7)
        if hasattr(self, "_hidden_text") and self._hidden_text:
            # Render in white color on white background (invisible to human eye, extractable by OCR)
            self.setFont("Helvetica", 1)  # 1pt tiny font
            self.setFillColor(colors.white)
            self.drawString(50, 45, str(self._hidden_text))

        self.restoreState()


def render_pdf_to_bytes(spec: ScenarioDocSpec) -> bytes:
    """Render a ScenarioDocSpec to deterministic PDF bytes."""
    buf = io.BytesIO()

    # Determine page size and margins based on layout
    is_landscape = spec.layout_name == "landscape_industrial"
    pagesize = landscape(A4) if is_landscape else A4
    page_w, _ = pagesize

    # If this is a scanned variant, render via scanner image and embed into PDF
    if spec.is_scanned:
        line_dicts = [
            {
                "line_no": str(line_item.line_no),
                "item_code": line_item.item_code,
                "description": line_item.description,
                "qty": str(line_item.qty),
                "uom": line_item.uom,
                "unit_price": f"{line_item.unit_price:.2f}",
                "line_total": f"{line_item.line_total:.2f}",
            }
            for line_item in spec.lines
        ]
        totals_dict = {
            "Subtotal": f"{spec.subtotal:.2f}",
            "VAT (5%)": f"{spec.vat:.2f}",
            "Total": f"{spec.total:.2f}",
        }
        scan_img = create_scanned_image(
            title=spec.doc_type.replace("_", " "),
            doc_type=spec.doc_type,
            vendor_name=spec.vendor_name,
            vendor_trn=spec.vendor_trn,
            doc_number=spec.document_number,
            doc_date=spec.document_date,
            lines=line_dicts,
            totals=totals_dict,
        )

        img_buf = io.BytesIO()
        scan_img.save(img_buf, format="PNG")
        img_buf.seek(0)

        # Build single page PDF containing the scanned image
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=20,
            rightMargin=20,
            topMargin=20,
            bottomMargin=40,
            invariant=True,
        )

        def make_scanned_canvas(*args: Any, **kwargs: Any) -> SyntheticDocCanvas:
            c = SyntheticDocCanvas(*args, **kwargs)
            if spec.hidden_text:
                c._hidden_text = spec.hidden_text
            return c

        scanned_story = [PlatypusImage(img_buf, width=A4[0] - 40, height=A4[1] - 80)]
        doc.build(scanned_story, canvasmaker=make_scanned_canvas)
        return buf.getvalue()

    # Standard vector PDF rendering
    doc = SimpleDocTemplate(
        buf,
        pagesize=pagesize,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=48,
        invariant=True,
    )

    def make_canvas(*args: Any, **kwargs: Any) -> SyntheticDocCanvas:
        c = SyntheticDocCanvas(*args, **kwargs)
        if spec.hidden_text:
            c._hidden_text = spec.hidden_text
        return c

    # Build story elements based on layout style
    story: list[Any] = []
    layout = spec.layout_name

    # 1. Colors & styling by layout
    if layout == "modern_tech":
        primary_color = colors.HexColor("#1E3A8A")  # Royal blue
        secondary_color = colors.HexColor("#3B82F6")
        accent_bg = colors.HexColor("#EFF6FF")
    elif layout == "classic_corporate":
        primary_color = colors.HexColor("#0F172A")  # Deep slate/black
        secondary_color = colors.HexColor("#475569")
        accent_bg = colors.HexColor("#F8FAFC")
    elif layout == "minimalist_slate":
        primary_color = colors.HexColor("#334155")  # Slate
        secondary_color = colors.HexColor("#64748B")
        accent_bg = colors.HexColor("#F1F5F9")
    elif layout == "landscape_industrial":
        primary_color = colors.HexColor("#164E63")  # Deep cyan
        secondary_color = colors.HexColor("#0891B2")
        accent_bg = colors.HexColor("#ECFEFF")
    else:  # rugged_border
        primary_color = colors.HexColor("#78350F")  # Amber / earth
        secondary_color = colors.HexColor("#B45309")
        accent_bg = colors.HexColor("#FEF3C7")

    title_text = spec.doc_type.replace("_", " ").upper()
    meta_val_style = ParagraphStyle(
        "MetaVal",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.black,
    )

    # Header section: Vendor info and Document info
    vendor_lines = [
        f"<b>{spec.vendor_name}</b>",
        f"TRN: {spec.vendor_trn}" if spec.vendor_trn else "<b>TRN: [NOT PROVIDED]</b>",
        spec.vendor_address or "Abu Dhabi, United Arab Emirates",
    ]
    if spec.vendor_email:
        vendor_lines.append(f"Email: {spec.vendor_email}")
    if spec.vendor_phone:
        vendor_lines.append(f"Phone: {spec.vendor_phone}")

    doc_info_lines = [
        f"<b>{title_text}</b>",
        f"<b>Number:</b> {spec.document_number}",
        f"<b>Date:</b> {spec.document_date}",
        f"<b>Currency:</b> {spec.currency}",
    ]
    if spec.po_number:
        doc_info_lines.append(f"<b>PO Number:</b> {spec.po_number}")
    if spec.pr_number:
        doc_info_lines.append(f"<b>PR Number:</b> {spec.pr_number}")
    if spec.payment_terms:
        doc_info_lines.append(f"<b>Payment Terms:</b> {spec.payment_terms}")
    if spec.due_date:
        doc_info_lines.append(f"<b>Due Date:</b> {spec.due_date}")
    if spec.lead_time_days:
        doc_info_lines.append(f"<b>Delivery Lead Time:</b> {spec.lead_time_days} days")

    header_table_data = [
        [
            Paragraph("<br/>".join(vendor_lines), meta_val_style),
            Paragraph("<br/>".join(doc_info_lines), meta_val_style),
        ]
    ]

    col_w = (page_w - 72) / 2.0
    header_table = Table(header_table_data, colWidths=[col_w, col_w])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, 0), accent_bg),
                ("BACKGROUND", (1, 0), (1, 0), colors.white),
                ("BOX", (0, 0), (0, 0), 0.5, secondary_color),
                ("BOX", (1, 0), (1, 0), 0.5, primary_color),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 14))

    # Customer info block (Bill To / Ship To)
    customer_html = (
        f"<b>Bill To:</b> {spec.customer_name}<br/>"
        f"<b>Address:</b> {spec.customer_address}<br/>"
        f"<b>Country:</b> United Arab Emirates"
    )
    story.append(Paragraph(customer_html, meta_val_style))
    story.append(Spacer(1, 14))

    # Line Items Table
    th_style = ParagraphStyle(
        "TH", fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=colors.white
    )
    td_style = ParagraphStyle(
        "TD", fontName="Helvetica", fontSize=8.5, leading=11, textColor=colors.black
    )
    td_num_style = ParagraphStyle(
        "TDNum", fontName="Helvetica", fontSize=8.5, leading=11, alignment=2, textColor=colors.black
    )

    if is_landscape:
        table_headers = [
            Paragraph("Item", th_style),
            Paragraph("Code", th_style),
            Paragraph("Description", th_style),
            Paragraph("Qty", th_style),
            Paragraph("UOM", th_style),
            Paragraph("Unit Price (AED)", th_style),
            Paragraph("VAT %", th_style),
            Paragraph("Total (AED)", th_style),
        ]
        col_widths = [35, 80, 320, 45, 45, 95, 55, 95]
    else:
        table_headers = [
            Paragraph("#", th_style),
            Paragraph("Item Code", th_style),
            Paragraph("Description", th_style),
            Paragraph("Qty", th_style),
            Paragraph("UOM", th_style),
            Paragraph("Rate (AED)", th_style),
            Paragraph("Amount (AED)", th_style),
        ]
        available_w = page_w - 72
        col_widths = [25, 75, available_w - (25 + 75 + 40 + 40 + 70 + 80), 40, 40, 70, 80]

    rows: list[list[Any]] = [table_headers]

    for item in spec.lines:
        if is_landscape:
            row = [
                Paragraph(str(item.line_no), td_style),
                Paragraph(item.item_code, td_style),
                Paragraph(item.description, td_style),
                Paragraph(str(item.qty), td_num_style),
                Paragraph(item.uom, td_style),
                Paragraph(f"{item.unit_price:.2f}", td_num_style),
                Paragraph(f"{item.vat_rate:.0f}%", td_num_style),
                Paragraph(f"{item.line_total:.2f}", td_num_style),
            ]
        else:
            row = [
                Paragraph(str(item.line_no), td_style),
                Paragraph(item.item_code, td_style),
                Paragraph(item.description, td_style),
                Paragraph(str(item.qty), td_num_style),
                Paragraph(item.uom, td_style),
                Paragraph(f"{item.unit_price:.2f}", td_num_style),
                Paragraph(f"{item.line_total:.2f}", td_num_style),
            ]
        rows.append(row)

    lines_table = Table(rows, colWidths=col_widths, repeatRows=1)
    lines_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), primary_color),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, accent_bg]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(lines_table)
    story.append(Spacer(1, 14))

    # Summary Totals Block
    tot_label = ParagraphStyle(
        "TotLbl", fontName="Helvetica-Bold", fontSize=9, leading=12, alignment=2
    )
    tot_val = ParagraphStyle("TotVal", fontName="Helvetica", fontSize=9, leading=12, alignment=2)
    tot_grand = ParagraphStyle(
        "TotGrd",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        alignment=2,
        textColor=primary_color,
    )

    summary_data = [
        [Paragraph("Subtotal:", tot_label), Paragraph(f"{spec.subtotal:.2f} AED", tot_val)],
        [Paragraph("VAT (5%):", tot_label), Paragraph(f"{spec.vat:.2f} AED", tot_val)],
        [Paragraph("Total Amount:", tot_grand), Paragraph(f"{spec.total:.2f} AED", tot_grand)],
    ]
    summary_col_w = 120
    summary_table = Table(summary_data, colWidths=[120, summary_col_w], hAlign="RIGHT")
    summary_table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 1), (-1, 1), 1, primary_color),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 14))

    # Remarks / Injections / Notes
    if spec.injection_expected and spec.injection_snippet and spec.injection_type != "hidden_text":
        story.append(
            Paragraph(
                f"<b>Special Remarks & Terms:</b> {spec.injection_snippet}",
                ParagraphStyle(
                    "Remarks",
                    fontName="Helvetica-Oblique",
                    fontSize=8.5,
                    leading=11,
                    textColor=colors.HexColor("#475569"),
                ),
            )
        )
    elif spec.notes:
        story.append(
            Paragraph(
                f"<b>Notes:</b> {spec.notes}",
                ParagraphStyle(
                    "Notes",
                    fontName="Helvetica",
                    fontSize=8,
                    leading=10,
                    textColor=colors.HexColor("#64748B"),
                ),
            )
        )

    doc.build(story, canvasmaker=make_canvas)
    return buf.getvalue()
