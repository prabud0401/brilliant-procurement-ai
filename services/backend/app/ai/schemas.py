"""Pydantic schemas for OCR results and strict structured extraction per design 6.2."""

from __future__ import annotations

import copy
from typing import Any

from pydantic import BaseModel, Field

KNOWN_HEADER_FIELDS: list[str] = [
    "vendor_name",
    "vendor_trn",
    "document_number",
    "document_date",
    "po_number",
    "currency",
    "payment_terms",
    "due_date",
    "subtotal",
    "vat_amount",
    "total",
    "lead_time_days",
]


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
    raw_result: dict[str, Any] | None = None


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


class AnswerResponse(BaseModel):
    sentences: list[AnswerSentence] = Field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None


class AnswerDraft(BaseModel):
    sentences: list[AnswerSentence] = Field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int | None = None


def to_strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model to an Azure OpenAI strict-compatible JSON schema.

    Inlines $defs/$ref, ensures additionalProperties: false on all objects,
    requires all properties on objects (optional fields expressed as nullable types),
    and strips unsupported schema keywords (default, format, pattern, minimum, etc.).
    """
    raw_schema = model.model_json_schema()
    defs = raw_schema.pop("$defs", {})

    def resolve_refs(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref_key = node["$ref"].split("/")[-1]
                target = copy.deepcopy(defs[ref_key])
                return resolve_refs(target)
            return {k: resolve_refs(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve_refs(item) for item in node]
        return node

    schema = resolve_refs(raw_schema)

    unsupported_keys = {
        "default",
        "title",
        "format",
        "pattern",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "uniqueItems",
        "$schema",
    }

    def clean_and_strict(node: Any) -> Any:
        if not isinstance(node, dict):
            if isinstance(node, list):
                return [clean_and_strict(x) for x in node]
            return node

        cleaned = {k: clean_and_strict(v) for k, v in node.items() if k not in unsupported_keys}

        is_object = (
            cleaned.get("type") == "object"
            or "properties" in cleaned
            or "additionalProperties" in cleaned
        )

        if is_object:
            cleaned["type"] = "object"
            cleaned["additionalProperties"] = False

            if (
                "additionalProperties" in node
                and isinstance(node["additionalProperties"], dict)
                and "properties" not in cleaned
            ):
                val_schema = clean_and_strict(node["additionalProperties"])
                cleaned["properties"] = {
                    fname: copy.deepcopy(val_schema) for fname in KNOWN_HEADER_FIELDS
                }

            props = cleaned.get("properties", {})
            cleaned["required"] = list(props.keys())

        return cleaned

    res = clean_and_strict(schema)
    assert isinstance(res, dict)
    return res
