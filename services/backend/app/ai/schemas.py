"""Pydantic schemas for OCR results and strict structured extraction per design 6.2."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OCRWord(BaseModel):
    content: str
    polygon: list[float] = Field(default_factory=list)
    confidence: float = 1.0


class OCRLine(BaseModel):
    content: str
    polygon: list[float] = Field(default_factory=list)
    spans: list[dict[str, int]] = Field(default_factory=list)


class OCRPage(BaseModel):
    page_number: int
    words: list[OCRWord] = Field(default_factory=list)
    lines: list[OCRLine] = Field(default_factory=list)
    angle: float = 0.0
    width: float = 8.5
    height: float = 11.0
    unit: str = "inch"


class OCRResult(BaseModel):
    content: str
    pages: list[OCRPage] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)


class FieldValue(BaseModel):
    value: str | None = None
    page: int = 1
    source_text: str | None = None


class ExtractionLineItem(BaseModel):
    line_no: int
    item_code: str | None = None
    description: str | None = None
    qty: str | None = None
    uom: str | None = None
    unit_price: str | None = None
    discount: str | None = None
    vat_rate: str | None = None
    line_total: str | None = None
    page: int = 1
    source_text: str | None = None


class ExtractionResult(BaseModel):
    doc_type: str
    header: dict[str, FieldValue | None]
    lines: list[ExtractionLineItem] = Field(default_factory=list)


class RetrievedChunk(BaseModel):
    id: str
    document_id: str
    document_title: str
    page: int
    chunk_no: int
    text: str
    score: float = 0.0


class AnswerSentence(BaseModel):
    text: str
    chunk_ids: list[str] = Field(default_factory=list)


class AnswerDraft(BaseModel):
    sentences: list[AnswerSentence] = Field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int | None = None
