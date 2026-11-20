"""Unit tests for F01: live provider reasoning parameters, cost table, and fixtures."""

from __future__ import annotations

import json
import time
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.ai.cost import (
    MODEL_PRICES_USD_PER_1M,
    calculate_cost_aed,
    calculate_cost_usd,
    get_model_token_rates_usd,
)
from app.ai.providers.live import (
    LiveAnswerWriter,
    LiveDocumentAnalyzer,
    LiveExplanationWriter,
    LiveLlmClient,
    _throttle_docintel,
    reset_docintel_throttle,
)
from app.ai.providers.replay import ReplayDocumentAnalyzer, ReplayLlmClient
from app.ai.schemas import (
    AnswerResponse,
    ExtractionResult,
    OCRResult,
    RetrievedChunk,
    to_strict_json_schema,
)
from app.core.errors import ProblemException
from eval.runner import CostLimitExceeded, RunningCostMeter


@pytest.mark.unit
def test_live_openai_parameters_reasoning_model() -> None:
    """Verify live client sends max_completion_tokens & reasoning_effort."""
    mock_chat_completion = MagicMock()
    mock_chat_completion.choices = [
        MagicMock(
            finish_reason="stop",
            message=MagicMock(content="invoice"),
        )
    ]
    mock_chat_completion.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

    # 1. Test classify
    llm_client = LiveLlmClient()
    llm_client.endpoint = "https://fake.openai.azure.com"
    llm_client.key = "fake-key"
    llm_client.deployment = "gpt-5-mini"

    with patch("app.ai.providers.live.create_azure_openai_client") as mock_create_client:
        mock_openai = MagicMock()
        mock_create_client.return_value = mock_openai
        mock_openai.chat.completions.create.return_value = mock_chat_completion

        label = llm_client.classify("Invoice Number: INV-001\nTotal: 100 AED")
        assert label == "invoice"

        mock_openai.chat.completions.create.assert_called_once()
        _, kwargs = mock_openai.chat.completions.create.call_args
        assert kwargs["model"] == "gpt-5-mini"
        assert kwargs["max_completion_tokens"] == 512
        assert kwargs["reasoning_effort"] == "low"
        assert "temperature" not in kwargs
        assert "max_tokens" not in kwargs

    # 2. Test extract
    extract_json = json.dumps(
        {
            "doc_type": "invoice",
            "header": {"vendor_name": {"value": "Test LLC", "page": 1, "source_text": "Test LLC"}},
            "lines": [],
        }
    )
    mock_extract_completion = MagicMock()
    mock_extract_completion.choices = [
        MagicMock(
            finish_reason="stop",
            message=MagicMock(content=extract_json),
        )
    ]
    mock_extract_completion.usage = MagicMock(prompt_tokens=500, completion_tokens=250)

    with patch("app.ai.providers.live.create_azure_openai_client") as mock_create_client:
        mock_openai = MagicMock()
        mock_create_client.return_value = mock_openai
        mock_openai.chat.completions.create.return_value = mock_extract_completion

        ocr_dummy = OCRResult(content="Test content", pages=[], documents=[], tables=[])
        res, meta = llm_client.extract(ocr_dummy, "invoice", doc_id="test-doc")
        assert res.doc_type == "invoice"
        assert meta["tokens_in"] == 500
        assert meta["tokens_out"] == 250

        mock_openai.chat.completions.create.assert_called_once()
        _, kwargs = mock_openai.chat.completions.create.call_args
        assert kwargs["model"] == "gpt-5-mini"
        assert kwargs["max_completion_tokens"] == 16000
        assert kwargs["reasoning_effort"] == "low"
        assert kwargs["response_format"]["type"] == "json_schema"
        assert kwargs["response_format"]["json_schema"]["strict"] is True
        assert kwargs["response_format"]["json_schema"]["name"] == "extraction_result"
        assert "temperature" not in kwargs
        assert "max_tokens" not in kwargs

    # 3. Test Q&A Answer Writer
    qa_writer = LiveAnswerWriter()
    qa_writer.endpoint = "https://fake.openai.azure.com"
    qa_writer.key = "fake-key"
    qa_writer.deployment = "gpt-5-mini"

    qa_json = json.dumps(
        {
            "sentences": [{"text": "Total is AED 100", "chunk_ids": ["c1"]}],
            "refused": False,
            "refusal_reason": None,
        }
    )
    mock_qa_completion = MagicMock()
    mock_qa_completion.choices = [
        MagicMock(finish_reason="stop", message=MagicMock(content=qa_json))
    ]
    mock_qa_completion.usage = MagicMock(prompt_tokens=300, completion_tokens=80)

    with patch("app.ai.providers.live.create_azure_openai_client") as mock_create_client:
        mock_openai = MagicMock()
        mock_create_client.return_value = mock_openai
        mock_openai.chat.completions.create.return_value = mock_qa_completion

        chunk = RetrievedChunk(
            id="c1",
            document_id="d1",
            document_title="Invoice",
            page=1,
            chunk_no=1,
            text="Total: AED 100",
            score=0.9,
        )
        draft = qa_writer.answer("What is the total?", [chunk])
        assert not draft.refused
        assert len(draft.sentences) == 1

        mock_openai.chat.completions.create.assert_called_once()
        _, kwargs = mock_openai.chat.completions.create.call_args
        assert kwargs["model"] == "gpt-5-mini"
        assert kwargs["max_completion_tokens"] == 4000
        assert kwargs["reasoning_effort"] == "low"
        assert kwargs["response_format"]["type"] == "json_schema"
        assert kwargs["response_format"]["json_schema"]["strict"] is True
        assert kwargs["response_format"]["json_schema"]["name"] == "answer_response"
        assert "temperature" not in kwargs
        assert "max_tokens" not in kwargs

    # 4. Test Explanation Writer
    exp_writer = LiveExplanationWriter()
    exp_writer.endpoint = "https://fake.openai.azure.com"
    exp_writer.key = "fake-key"
    exp_writer.deployment = "gpt-5-mini"

    mock_exp_completion = MagicMock()
    mock_exp_completion.choices = [
        MagicMock(finish_reason="stop", message=MagicMock(content="Vendor A is recommended."))
    ]

    with patch("app.ai.providers.live.create_azure_openai_client") as mock_create_client:
        mock_openai = MagicMock()
        mock_create_client.return_value = mock_openai
        mock_openai.chat.completions.create.return_value = mock_exp_completion

        explanation = exp_writer.explain({"winner_vendor_id": "v1"})
        assert "Vendor A is recommended." in explanation

        mock_openai.chat.completions.create.assert_called_once()
        _, kwargs = mock_openai.chat.completions.create.call_args
        assert kwargs["model"] == "gpt-5-mini"
        assert kwargs["max_completion_tokens"] == 4000
        assert kwargs["reasoning_effort"] == "low"
        assert "temperature" not in kwargs
        assert "max_tokens" not in kwargs


@pytest.mark.unit
def test_truncated_and_empty_response_handling() -> None:
    """Verify that finish_reason='length' or empty content raises ProblemException."""
    client = LiveLlmClient()
    client.endpoint = "https://fake.openai.azure.com"
    client.key = "fake-key"

    # Truncated classification response
    with patch("app.ai.providers.live.create_azure_openai_client") as mock_create:
        mock_openai = MagicMock()
        mock_create.return_value = mock_openai
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(finish_reason="length", message=MagicMock(content="inv"))]
        )

        with pytest.raises(ProblemException) as exc_info:
            client.classify("some doc text")
        assert exc_info.value.status_code == 502
        assert exc_info.value.code == "AI_RESPONSE_TRUNCATED"

    # Empty extraction response
    with patch("app.ai.providers.live.create_azure_openai_client") as mock_create:
        mock_openai = MagicMock()
        mock_create.return_value = mock_openai
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(finish_reason="stop", message=MagicMock(content="   "))]
        )

        ocr_dummy = OCRResult(content="text", pages=[], documents=[], tables=[])
        with pytest.raises(ProblemException) as exc_info:
            client.extract(ocr_dummy, "quote")
        assert exc_info.value.status_code == 502
        assert exc_info.value.code == "AI_RESPONSE_EMPTY"

    # Truncated Q&A response
    qa_writer = LiveAnswerWriter()
    qa_writer.endpoint = "https://fake.openai.azure.com"
    qa_writer.key = "fake-key"

    with patch("app.ai.providers.live.create_azure_openai_client") as mock_create:
        mock_openai = MagicMock()
        mock_create.return_value = mock_openai
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(finish_reason="length", message=MagicMock(content='{"sentences":'))]
        )

        with pytest.raises(ProblemException) as exc_info:
            qa_writer.answer("Question?", [])
        assert exc_info.value.status_code == 502
        assert exc_info.value.code == "AI_RESPONSE_TRUNCATED"

    # Empty explanation response
    exp_writer = LiveExplanationWriter()
    exp_writer.endpoint = "https://fake.openai.azure.com"
    exp_writer.key = "fake-key"

    with patch("app.ai.providers.live.create_azure_openai_client") as mock_create:
        mock_openai = MagicMock()
        mock_create.return_value = mock_openai
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(finish_reason="stop", message=MagicMock(content="   "))]
        )

        with pytest.raises(ProblemException) as exc_info:
            exp_writer.explain({"winner_vendor_id": "v1"})
        assert exc_info.value.status_code == 502
        assert exc_info.value.code == "AI_RESPONSE_EMPTY"

    # Empty choices explanation response
    with patch("app.ai.providers.live.create_azure_openai_client") as mock_create:
        mock_openai = MagicMock()
        mock_create.return_value = mock_openai
        mock_openai.chat.completions.create.return_value = MagicMock(choices=[])

        with pytest.raises(ProblemException) as exc_info:
            exp_writer.explain({"winner_vendor_id": "v1"})
        assert exc_info.value.status_code == 502
        assert exc_info.value.code == "AI_RESPONSE_EMPTY"

    # Truncated explanation response
    with patch("app.ai.providers.live.create_azure_openai_client") as mock_create:
        mock_openai = MagicMock()
        mock_create.return_value = mock_openai
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(finish_reason="length", message=MagicMock(content="Vendor"))]
        )

        with pytest.raises(ProblemException) as exc_info:
            exp_writer.explain({"winner_vendor_id": "v1"})
        assert exc_info.value.status_code == 502
        assert exc_info.value.code == "AI_RESPONSE_TRUNCATED"


@pytest.mark.unit
def test_price_table_and_unknown_model_fallback() -> None:
    """Verify price table rates and conservative fallback for unknown models."""
    # 1. gpt-5-mini: 0.25 in / 2.00 out per 1M USD
    r_in, r_out = get_model_token_rates_usd("gpt-5-mini")
    assert r_in == Decimal("0.00000025")
    assert r_out == Decimal("0.00000200")

    cost_usd = calculate_cost_usd(1_000_000, 1_000_000, "gpt-5-mini")
    assert cost_usd == Decimal("2.25")

    cost_aed = calculate_cost_aed(1_000_000, 1_000_000, "gpt-5-mini")
    expected_aed = (Decimal("2.25") * Decimal("3.6725")).quantize(Decimal("0.0001"))
    assert cost_aed == expected_aed

    # 2. gpt-5.4-mini: 0.75 in / 4.50 out per 1M USD
    r_in, r_out = get_model_token_rates_usd("gpt-5.4-mini")
    assert r_in == Decimal("0.00000075")
    assert r_out == Decimal("0.00000450")

    # 3. gpt-4o-mini: 0.15 in / 0.60 out per 1M USD
    r_in, r_out = get_model_token_rates_usd("gpt-4o-mini")
    assert r_in == Decimal("0.00000015")
    assert r_out == Decimal("0.00000060")

    # 4. text-embedding-3-small: 0.02 in
    r_in, r_out = get_model_token_rates_usd("text-embedding-3-small")
    assert r_in == Decimal("0.00000002")
    assert r_out == Decimal("0.00")

    # 5. Unknown model: falls back to highest listed rates (0.75 in / 4.50 out)
    r_in_unk, r_out_unk = get_model_token_rates_usd("future-unlisted-model-x")
    max_in = max(p["input"] for p in MODEL_PRICES_USD_PER_1M.values()) / Decimal("1000000")
    max_out = max(p["output"] for p in MODEL_PRICES_USD_PER_1M.values()) / Decimal("1000000")
    assert r_in_unk == max_in == Decimal("0.00000075")
    assert r_out_unk == max_out == Decimal("0.00000450")


@pytest.mark.unit
def test_running_cost_meter_aborts_at_cap() -> None:
    """Verify running cost meter tracks spend and cleanly aborts at max_cost_usd cap."""
    meter = RunningCostMeter(max_cost_usd=0.01, default_model="gpt-5-mini")

    # Usage within budget: 10,000 in, 1,000 out on gpt-5-mini
    # Cost = 10,000 * 0.00000025 + 1,000 * 0.000002 = 0.0025 + 0.002 = 0.0045 USD
    cost1 = meter.record_usage(10_000, 1_000)
    assert round(cost1, 5) == 0.0045
    assert round(meter.total_cost_usd, 5) == 0.0045
    assert meter.tokens_in == 10_000
    assert meter.tokens_out == 1_000

    # Next call exceeds cap of 0.01: 20,000 in, 3,000 out
    # Cost = 20,000 * 0.00000025 + 3,000 * 0.000002 = 0.005 + 0.006 = 0.011 USD
    # Total would be 0.0045 + 0.011 = 0.0155 USD > 0.01 USD
    with pytest.raises(CostLimitExceeded) as exc_info:
        meter.record_usage(20_000, 3_000)

    assert "exceeds maximum allowed budget of $0.0100 USD" in str(exc_info.value)
    # Totals are preserved on meter
    assert meter.tokens_in == 30_000
    assert meter.tokens_out == 4_000
    assert meter.total_cost_usd > 0.01


@pytest.mark.unit
def test_docintel_throttle_and_retry() -> None:
    """Verify Document Intelligence F0 throttle (>= 1s) and retry on 429 backoff."""
    # 1. Throttle verification
    reset_docintel_throttle()
    t0 = time.monotonic()
    _throttle_docintel(min_interval=0.05)
    _throttle_docintel(min_interval=0.05)
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.045  # Satisfies at least 50ms throttle

    # 2. Retry on 429 verification
    analyzer = LiveDocumentAnalyzer()
    analyzer.endpoint = "https://fake.cognitiveservices.azure.com"
    analyzer.key = "fake-key"

    class Fake429Error(Exception):
        status_code = 429

    mock_poller = MagicMock()
    mock_poller.result.return_value = MagicMock(
        pages=[], documents=[], tables=[], content="text", api_version="2024-02-29-preview"
    )

    with (
        patch("azure.ai.documentintelligence.DocumentIntelligenceClient") as mock_di_client,
        patch("azure.core.credentials.AzureKeyCredential"),
        patch("time.sleep") as mock_sleep,
    ):
        inst = mock_di_client.return_value
        # Raise 429 on attempts 1 and 2, then succeed on attempt 3
        inst.begin_analyze_document.side_effect = [
            Fake429Error("Too many requests"),
            Fake429Error("Too many requests"),
            mock_poller,
        ]

        result = analyzer.analyze(b"%PDF-test", "application/pdf")
        assert result is not None
        assert inst.begin_analyze_document.call_count == 3
        # Assert backoff sleep was called twice
        assert mock_sleep.call_count >= 2

    # 3. Exhaustion on 3 attempts -> raises ProblemException 429
    with (
        patch("azure.ai.documentintelligence.DocumentIntelligenceClient") as mock_di_client,
        patch("azure.core.credentials.AzureKeyCredential"),
        patch("time.sleep"),
    ):
        inst = mock_di_client.return_value
        inst.begin_analyze_document.side_effect = Fake429Error("Rate limit exceeded")

        with pytest.raises(ProblemException) as exc_info:
            analyzer.analyze(b"%PDF-test", "application/pdf")
        assert exc_info.value.status_code == 429
        assert exc_info.value.code == "AI_RATE_LIMIT_EXCEEDED"
        assert inst.begin_analyze_document.call_count == 3


@pytest.mark.unit
def test_fixture_recording_roundtrip(tmp_path: Path) -> None:
    """Verify live result formats round-trip through Replay providers."""
    doc_id = "test-doc-roundtrip"

    # 1. Build a synthetic Document Intelligence analyzeResult fixture
    di_fixture = {
        "status": "succeeded",
        "createdDateTime": "2026-11-20T12:00:00Z",
        "lastUpdatedDateTime": "2026-11-20T12:00:00Z",
        "analyzeResult": {
            "apiVersion": "2024-02-29-preview",
            "modelId": "prebuilt-layout",
            "stringIndexType": "textElements",
            "content": "Gulf Line IT Trading\nInvoice No: INV-9999\nTotal: 5000.00",
            "pages": [
                {
                    "pageNumber": 1,
                    "angle": 0.0,
                    "width": 8.5,
                    "height": 11.0,
                    "unit": "inch",
                    "words": [
                        {
                            "content": "Gulf",
                            "polygon": [1.0, 1.0, 2.0, 1.0, 2.0, 1.2, 1.0, 1.2],
                            "confidence": 0.99,
                        }
                    ],
                    "lines": [
                        {
                            "content": "Gulf Line IT Trading",
                            "polygon": [1.0, 1.0, 4.0, 1.0, 4.0, 1.2, 1.0, 1.2],
                            "spans": [{"offset": 0, "length": 20}],
                        }
                    ],
                }
            ],
            "documents": [],
            "tables": [],
        },
    }

    # 2. Build a synthetic OpenAI chat completion fixture
    extraction_content = json.dumps(
        {
            "doc_type": "invoice",
            "header": {
                "vendor_name": {
                    "value": "Gulf Line IT Trading",
                    "page": 1,
                    "source_text": "Gulf Line IT Trading",
                },
                "document_number": {
                    "value": "INV-9999",
                    "page": 1,
                    "source_text": "Invoice No: INV-9999",
                },
                "total": {
                    "value": "5000.00",
                    "page": 1,
                    "source_text": "Total: 5000.00",
                },
            },
            "lines": [
                {
                    "line_no": 1,
                    "description": "IT Support Services",
                    "qty": "1",
                    "unit_price": "5000.00",
                    "line_total": "5000.00",
                    "page": 1,
                    "source_text": "IT Support Services 1 5000.00",
                }
            ],
        }
    )

    openai_fixture = {
        "id": f"chatcmpl-{doc_id}",
        "object": "chat.completion",
        "created": 1732040000,
        "model": "gpt-5-mini",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": extraction_content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 1400,
            "completion_tokens": 350,
            "total_tokens": 1750,
        },
    }

    # Save to tmp replay directory
    di_path = tmp_path / f"{doc_id}.di.json"
    openai_path = tmp_path / f"{doc_id}.openai.json"

    with open(di_path, "w", encoding="utf-8") as f:
        json.dump(di_fixture, f, indent=2)

    with open(openai_path, "w", encoding="utf-8") as f:
        json.dump(openai_fixture, f, indent=2)

    # 3. Read back with ReplayDocumentAnalyzer
    replay_analyzer = ReplayDocumentAnalyzer(replay_dir=tmp_path)
    ocr_result = replay_analyzer.analyze(
        file_bytes=b"",
        mime="application/pdf",
        doc_id=doc_id,
    )
    assert "Gulf Line IT Trading" in ocr_result.content
    assert len(ocr_result.pages) == 1
    assert ocr_result.pages[0].page_number == 1
    assert ocr_result.pages[0].words[0].content == "Gulf"
    assert ocr_result.pages[0].words[0].confidence == 0.99
    assert ocr_result.pages[0].lines[0].content == "Gulf Line IT Trading"

    # 4. Read back with ReplayLlmClient
    replay_llm = ReplayLlmClient(replay_dir=tmp_path)
    ext_result, metadata = replay_llm.extract(ocr_result, "invoice", doc_id=doc_id)

    assert ext_result.doc_type == "invoice"
    assert ext_result.header["vendor_name"] is not None
    assert ext_result.header["vendor_name"].value == "Gulf Line IT Trading"
    assert ext_result.header["document_number"] is not None
    assert ext_result.header["document_number"].value == "INV-9999"
    assert ext_result.header["total"] is not None
    assert ext_result.header["total"].value == "5000.00"

    assert len(ext_result.lines) == 1
    assert ext_result.lines[0].description == "IT Support Services"
    assert ext_result.lines[0].line_total == "5000.00"

    assert metadata["tokens_in"] == 1400
    assert metadata["tokens_out"] == 350
    assert metadata["model"] == "gpt-5-mini"


def assert_strict_schema_compatible(schema: dict[str, Any]) -> None:
    """Recursively check that schema is Azure OpenAI strict-compatible."""
    assert "$ref" not in json.dumps(schema)
    assert "$defs" not in schema

    def check_node(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False, (
                    f"additionalProperties not False at {path}"
                )
                props = node.get("properties", {})
                req = node.get("required", [])
                assert set(props.keys()) == set(req), (
                    f"Object properties != required at {path}: {set(props.keys())} vs {set(req)}"
                )
            for k, v in node.items():
                check_node(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                check_node(item, f"{path}[{i}]")

    check_node(schema)


@pytest.mark.unit
def test_extraction_sends_strict_json_schema_and_field_guide() -> None:
    """Verify extract sends strict json_schema with ExtractionResult keys and field guide."""
    llm_client = LiveLlmClient()
    llm_client.endpoint = "https://fake.openai.azure.com"
    llm_client.key = "fake-key"
    llm_client.deployment = "gpt-5-mini"

    fake_response_dict = {
        "doc_type": "quote",
        "header": {
            "vendor_name": {"value": "Acme Corp", "page": 1, "source_text": "Acme Corp LLC"},
            "vendor_trn": {
                "value": "100000000000001",
                "page": 1,
                "source_text": "TRN: 100000000000001",
            },
            "document_number": {"value": "Q-999", "page": 1, "source_text": "Quote Q-999"},
            "document_date": {"value": "2026-11-20", "page": 1, "source_text": "2026-11-20"},
            "po_number": None,
            "currency": {"value": "AED", "page": 1, "source_text": "AED"},
            "payment_terms": {"value": "Net 30", "page": 1, "source_text": "Net 30"},
            "due_date": None,
            "subtotal": {"value": "1000.00", "page": 1, "source_text": "1000.00"},
            "vat_amount": {"value": "50.00", "page": 1, "source_text": "50.00"},
            "total": {"value": "1050.00", "page": 1, "source_text": "1050.00"},
        },
        "lines": [
            {
                "line_no": 1,
                "item_code": "IT-01",
                "description": "Standard Laptop",
                "qty": "1",
                "uom": "EA",
                "unit_price": "1000.00",
                "discount": "0.00",
                "vat_rate": "5",
                "line_total": "1000.00",
                "page": 1,
                "source_text": "Standard Laptop 1000.00",
            }
        ],
    }

    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(
            finish_reason="stop",
            message=MagicMock(content=json.dumps(fake_response_dict)),
        )
    ]
    mock_completion.usage = MagicMock(prompt_tokens=400, completion_tokens=150)

    with patch("app.ai.providers.live.create_azure_openai_client") as mock_create_client:
        mock_openai = MagicMock()
        mock_create_client.return_value = mock_openai
        mock_openai.chat.completions.create.return_value = mock_completion

        ocr_dummy = OCRResult(content="Document content text", pages=[], documents=[], tables=[])
        result, meta = llm_client.extract(ocr_dummy, "quote", doc_id="quote-1")

        # 1. Fake response validates with ExtractionResult.model_validate_json
        validated_direct = ExtractionResult.model_validate_json(json.dumps(fake_response_dict))
        assert validated_direct.doc_type == "quote"
        assert result.doc_type == "quote"
        assert result.header["vendor_name"] is not None
        assert result.header["vendor_name"].value == "Acme Corp"
        assert len(result.lines) == 1
        assert result.lines[0].item_code == "IT-01"

        # 2. Check call arguments
        mock_openai.chat.completions.create.assert_called_once()
        _, kwargs = mock_openai.chat.completions.create.call_args

        # 3. response_format check
        rf = kwargs["response_format"]
        assert rf["type"] == "json_schema"
        assert rf["json_schema"]["strict"] is True
        assert rf["json_schema"]["name"] == "extraction_result"

        # 4. Schema top-level keys
        schema = rf["json_schema"]["schema"]
        assert set(schema["properties"].keys()) == {"doc_type", "header", "lines"}

        # 5. Recursive strict check
        assert_strict_schema_compatible(schema)

        # 6. System prompt contains field guide, injection defence, and value-only rules
        messages = kwargs["messages"]
        system_msg = next(m["content"] for m in messages if m["role"] == "system")
        assert "field guide" in system_msg.lower()
        assert "vendor_name" in system_msg
        assert "page" in system_msg.lower()
        assert "source text" in system_msg.lower() or "source_text" in system_msg.lower()
        assert "data, not instructions" in system_msg
        assert "value only" in system_msg.lower()
        assert "legal/trading" in system_msg.lower()
        assert "plain numbers" in system_msg.lower()
        assert "iso" in system_msg.lower()


@pytest.mark.unit
def test_classification_normalises_odd_replies() -> None:
    """Verify that classification normalises various LLM responses and maps unknown to 'other'."""
    llm_client = LiveLlmClient()
    llm_client.endpoint = "https://fake.openai.azure.com"
    llm_client.key = "fake-key"
    llm_client.deployment = "gpt-5-mini"

    test_cases = [
        ("invoice", "invoice"),
        ("INVOICE", "invoice"),
        ("`invoice`", "invoice"),
        ("Invoice.", "invoice"),
        ("```\nquotation\n```", "quote"),
        ("quote", "quote"),
        ("Quotation", "quote"),
        ("'purchase_order'", "purchase_order"),
        ("Purchase Order", "purchase_order"),
        ("Document type: Purchase Order", "purchase_order"),
        ("PO", "purchase_order"),
        ("delivery_note", "delivery_note"),
        ("Delivery Note", "delivery_note"),
        ("DN", "delivery_note"),
        ("delivery note receipt", "delivery_note"),
        ("other", "other"),
        ("Receipt / Voucher", "other"),
        ("Unknown document", "other"),
        ("Bank statement", "other"),
    ]

    for raw_reply, expected_label in test_cases:
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(finish_reason="stop", message=MagicMock(content=raw_reply))
        ]
        with patch("app.ai.providers.live.create_azure_openai_client") as mock_create:
            mock_openai = MagicMock()
            mock_create.return_value = mock_openai
            mock_openai.chat.completions.create.return_value = mock_completion

            result_label = llm_client.classify("Some sample text")
            assert result_label == expected_label, (
                f"Failed for input '{raw_reply}': got '{result_label}', expected '{expected_label}'"
            )


@pytest.mark.unit
def test_qa_writer_sends_strict_json_schema() -> None:
    """Verify LiveAnswerWriter sends strict json_schema for AnswerResponse."""
    qa_writer = LiveAnswerWriter()
    qa_writer.endpoint = "https://fake.openai.azure.com"
    qa_writer.key = "fake-key"
    qa_writer.deployment = "gpt-5-mini"

    mock_qa_completion = MagicMock()
    mock_qa_completion.choices = [
        MagicMock(
            finish_reason="stop",
            message=MagicMock(
                content=json.dumps(
                    {
                        "sentences": [{"text": "Terms are Net 30", "chunk_ids": ["c1"]}],
                        "refused": False,
                        "refusal_reason": None,
                    }
                )
            ),
        )
    ]
    mock_qa_completion.usage = MagicMock(prompt_tokens=200, completion_tokens=50)

    with patch("app.ai.providers.live.create_azure_openai_client") as mock_create_client:
        mock_openai = MagicMock()
        mock_create_client.return_value = mock_openai
        mock_openai.chat.completions.create.return_value = mock_qa_completion

        chunk = RetrievedChunk(
            id="c1",
            document_id="d1",
            document_title="Quote Q-1042",
            page=1,
            chunk_no=1,
            text="Payment terms: Net 30",
            score=0.95,
        )

        draft = qa_writer.answer("What are the terms?", [chunk])
        assert not draft.refused
        assert len(draft.sentences) == 1
        assert draft.sentences[0].text == "Terms are Net 30"

        mock_openai.chat.completions.create.assert_called_once()
        _, kwargs = mock_openai.chat.completions.create.call_args

        rf = kwargs["response_format"]
        assert rf["type"] == "json_schema"
        assert rf["json_schema"]["strict"] is True
        assert rf["json_schema"]["name"] == "answer_response"

        schema = rf["json_schema"]["schema"]
        assert set(schema["properties"].keys()) == {"sentences", "refused", "refusal_reason"}
        assert_strict_schema_compatible(schema)
        assert_strict_schema_compatible(to_strict_json_schema(AnswerResponse))


@pytest.mark.unit
def test_structured_output_fixture_roundtrip(tmp_path: Path) -> None:
    """Verify structured output response fixtures roundtrip through ReplayLlmClient."""
    doc_id = "test-structured-fixture"
    structured_content = json.dumps(
        {
            "doc_type": "invoice",
            "header": {
                "vendor_name": {
                    "value": "Structured Vendor",
                    "page": 1,
                    "source_text": "Structured Vendor",
                },
                "vendor_trn": {
                    "value": "100000000000005",
                    "page": 1,
                    "source_text": "TRN 100000000000005",
                },
                "document_number": {"value": "INV-5555", "page": 1, "source_text": "INV-5555"},
                "document_date": {"value": "2026-11-15", "page": 1, "source_text": "2026-11-15"},
                "po_number": None,
                "currency": {"value": "AED", "page": 1, "source_text": "AED"},
                "payment_terms": None,
                "due_date": None,
                "subtotal": {"value": "2500.00", "page": 1, "source_text": "2500.00"},
                "vat_amount": {"value": "125.00", "page": 1, "source_text": "125.00"},
                "total": {"value": "2625.00", "page": 1, "source_text": "2625.00"},
            },
            "lines": [
                {
                    "line_no": 1,
                    "item_code": "SERV-01",
                    "description": "Consulting Services",
                    "qty": "10",
                    "uom": "HR",
                    "unit_price": "250.00",
                    "discount": "0.00",
                    "vat_rate": "5",
                    "line_total": "2500.00",
                    "page": 1,
                    "source_text": "Consulting Services 10 HR 250.00 2500.00",
                }
            ],
        }
    )

    openai_fixture = {
        "id": f"chatcmpl-{doc_id}",
        "object": "chat.completion",
        "created": 1732040000,
        "model": "gpt-5-mini",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": structured_content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 1500,
            "completion_tokens": 300,
            "total_tokens": 1800,
        },
    }

    openai_path = tmp_path / f"{doc_id}.openai.json"
    with open(openai_path, "w", encoding="utf-8") as f:
        json.dump(openai_fixture, f, indent=2)

    replay_llm = ReplayLlmClient(replay_dir=tmp_path)
    ocr_dummy = OCRResult(content="INV-5555 Structured Vendor", pages=[], documents=[], tables=[])

    result, meta = replay_llm.extract(ocr_dummy, "invoice", doc_id=doc_id)
    assert result.doc_type == "invoice"
    assert result.header["vendor_name"] is not None
    assert result.header["vendor_name"].value == "Structured Vendor"
    assert result.header["total"] is not None
    assert result.header["total"].value == "2625.00"
    assert len(result.lines) == 1
    assert result.lines[0].item_code == "SERV-01"
    assert meta["model"] == "gpt-5-mini"
