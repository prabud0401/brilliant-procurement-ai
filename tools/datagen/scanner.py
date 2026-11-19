"""Module for generating scanned/degraded document images with noise, blur and skew."""

from __future__ import annotations

import random
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont


def create_scanned_image(
    title: str,
    doc_type: str,
    vendor_name: str,
    vendor_trn: str,
    doc_number: str,
    doc_date: str,
    lines: list[dict[str, str]],
    totals: dict[str, str],
    footer_text: str = "SAMPLE – SYNTHETIC DATA",
    width: int = 1654,  # ~200 DPI A4
    height: int = 2338,
    seed: int = 42,
) -> Image.Image:
    """Render a simulated physical scanned paper page with blur, skew and noise."""
    rng = random.Random(seed)

    # 1. Base paper background (slightly off-white paper texture)
    img = Image.new("RGB", (width, height), color=(250, 250, 248))
    draw = ImageDraw.Draw(img)

    # Attempt to load a default TrueType font or fallback
    font_large: Any
    font_med_bold: Any
    font_med: Any
    font_small: Any
    font_footer: Any
    try:
        font_large = ImageFont.truetype("DejaVuSans-Bold.ttf", 38)
        font_med_bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
        font_med = ImageFont.truetype("DejaVuSans.ttf", 24)
        font_small = ImageFont.truetype("DejaVuSans.ttf", 20)
        font_footer = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
    except OSError:
        font_large = ImageFont.load_default()
        font_med_bold = font_large
        font_med = font_large
        font_small = font_large
        font_footer = font_large

    # 2. Draw document header
    y = 120
    draw.text((120, y), title.upper(), fill=(20, 20, 20), font=font_large)
    y += 60
    draw.line([(120, y), (width - 120, y)], fill=(60, 60, 60), width=3)
    y += 30

    draw.text((120, y), f"Vendor: {vendor_name}", fill=(30, 30, 30), font=font_med_bold)
    y += 40
    if vendor_trn:
        draw.text((120, y), f"TRN: {vendor_trn}", fill=(50, 50, 50), font=font_med)
        y += 35

    draw.text((120, y), f"Document No: {doc_number}", fill=(30, 30, 30), font=font_med)
    draw.text((width - 500, y), f"Date: {doc_date}", fill=(30, 30, 30), font=font_med)
    y += 60

    # 3. Draw table header
    draw.rectangle([(120, y), (width - 120, y + 45)], fill=(225, 225, 225))
    draw.text((135, y + 10), "Line", fill=(20, 20, 20), font=font_med_bold)
    draw.text((220, y + 10), "Code", fill=(20, 20, 20), font=font_med_bold)
    draw.text((450, y + 10), "Description", fill=(20, 20, 20), font=font_med_bold)
    draw.text((1050, y + 10), "Qty", fill=(20, 20, 20), font=font_med_bold)
    draw.text((1180, y + 10), "Unit Price", fill=(20, 20, 20), font=font_med_bold)
    draw.text((1380, y + 10), "Total (AED)", fill=(20, 20, 20), font=font_med_bold)
    y += 55

    # 4. Draw table rows
    for item in lines:
        draw.line([(120, y), (width - 120, y)], fill=(210, 210, 210), width=1)
        y += 10
        draw.text((135, y), str(item.get("line_no", "")), fill=(40, 40, 40), font=font_small)
        draw.text((220, y), str(item.get("item_code", "")), fill=(40, 40, 40), font=font_small)
        desc = str(item.get("description", ""))
        if len(desc) > 36:
            desc = desc[:33] + "..."
        draw.text((450, y), desc, fill=(40, 40, 40), font=font_small)
        draw.text((1050, y), f"{item.get('qty', '')} {item.get('uom', '')}", fill=(40, 40, 40), font=font_small)
        draw.text((1180, y), str(item.get("unit_price", "")), fill=(40, 40, 40), font=font_small)
        draw.text((1380, y), str(item.get("line_total", "")), fill=(40, 40, 40), font=font_small)
        y += 40

    draw.line([(120, y), (width - 120, y)], fill=(60, 60, 60), width=2)
    y += 40

    # 5. Draw totals
    for k, v in totals.items():
        draw.text((width - 600, y), f"{k}:", fill=(30, 30, 30), font=font_med_bold)
        draw.text((width - 320, y), f"{v} AED", fill=(30, 30, 30), font=font_med_bold)
        y += 40

    # 6. Draw footer
    draw.line([(120, height - 120), (width - 120, height - 120)], fill=(120, 120, 120), width=1)
    footer_bbox = draw.textbbox((0, 0), footer_text, font=font_footer)
    footer_w = footer_bbox[2] - footer_bbox[0]
    draw.text(((width - footer_w) // 2, height - 90), footer_text, fill=(100, 100, 100), font=font_footer)

    # 7. Apply scanner artifacts: Skew (rotation)
    angle = rng.uniform(0.6, 1.2)  # slight skew ~0.8 degrees
    img = img.rotate(angle, resample=Image.Resampling.BILINEAR, fillcolor=(245, 245, 242))

    # 8. Apply slight Gaussian blur (scanner lens softness)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))

    # 9. Add scanner salt-and-pepper / grain noise
    pixels = img.load()
    if pixels is not None:
        noise_count = int(width * height * 0.003)  # 0.3% pixels
        for _ in range(noise_count):
            rx = rng.randint(0, width - 1)
            ry = rng.randint(0, height - 1)
            val = rng.randint(180, 240)
            pixels[rx, ry] = (val, val, val)

    return img
