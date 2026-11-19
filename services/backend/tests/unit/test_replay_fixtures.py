"""Unit tests verifying replay fixture schema validity and confidence variation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _get_eval_data_dir() -> Path:
    if Path("eval/data").is_dir():
        return Path("eval/data")
    for parent in Path(__file__).resolve().parents:
        cand = parent / "eval" / "data"
        if cand.is_dir():
            return cand
    return Path("eval/data")


_EVAL_DATA_DIR = _get_eval_data_dir()


@pytest.mark.unit
def test_manifest_documents_have_replay_fixtures() -> None:
    """Every document in manifest.json must have corresponding DI and OpenAI replay fixtures."""
    manifest_file = _EVAL_DATA_DIR / "manifest.json"
    assert manifest_file.exists(), "eval/data/manifest.json missing"

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    docs = manifest.get("documents", [])
    assert len(docs) == 20, f"Expected 20 evaluation documents, found {len(docs)}"

    replay_dir = _EVAL_DATA_DIR / "replay"
    assert replay_dir.exists(), "eval/data/replay directory missing"

    for d in docs:
        doc_id = d["doc_id"]
        di_path = replay_dir / f"{doc_id}.di.json"
        openai_path = replay_dir / f"{doc_id}.openai.json"

        assert di_path.exists(), f"Missing DI fixture for {doc_id}"
        assert openai_path.exists(), f"Missing OpenAI fixture for {doc_id}"


@pytest.mark.unit
def test_di_fixture_structure() -> None:
    """Document Intelligence analyzeResult structure must match Azure API specifications."""
    replay_dir = _EVAL_DATA_DIR / "replay"
    di_files = list(replay_dir.glob("*.di.json"))
    assert len(di_files) >= 20

    low_conf_found = False

    for fpath in di_files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data.get("status") == "succeeded"
        ar = data.get("analyzeResult", {})
        assert "content" in ar
        assert "pages" in ar and len(ar["pages"]) > 0
        assert "words" in ar["pages"][0]
        assert "lines" in ar["pages"][0]
        assert "documents" in ar and len(ar["documents"]) > 0

        fields = ar["documents"][0].get("fields", {})
        assert "VendorName" in fields

        # Check for varied confidence below 0.80
        for fld_val in fields.values():
            if fld_val.get("confidence", 1.0) < 0.80:
                low_conf_found = True

    assert low_conf_found, (
        "Expected at least one field with confidence < 0.80 to exercise review workflow"
    )


@pytest.mark.unit
def test_openai_fixture_structure_and_extraction_schema() -> None:
    """OpenAI completions fixture must contain strict extraction JSON per design 6.2."""
    replay_dir = _EVAL_DATA_DIR / "replay"
    openai_files = list(replay_dir.glob("*.openai.json"))
    assert len(openai_files) >= 20

    for fpath in openai_files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data.get("object") == "chat.completion"
        assert "choices" in data and len(data["choices"]) > 0
        msg = data["choices"][0].get("message", {})
        assert msg.get("role") == "assistant"

        content_raw = msg.get("content", "")
        parsed = json.loads(content_raw)

        # Validate design 6.2 schema
        assert "doc_type" in parsed
        assert "header" in parsed
        header = parsed["header"]
        assert "vendor_name" in header and "value" in header["vendor_name"]
        assert "document_number" in header and "value" in header["document_number"]
        assert "document_date" in header and "value" in header["document_date"]
        assert "total" in header and "value" in header["total"]
        assert "lines" in parsed and isinstance(parsed["lines"], list)


@pytest.mark.unit
def test_replay_provider_lazy_resolution_and_missing_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replay provider resolves directory lazily and raises clear error when missing."""
    from app.ai.providers.replay import ReplayDocumentAnalyzer, ReplayLlmClient
    from app.core.config import settings

    # 1. Lazy: instantiating analyzer/client does not check or fail
    analyzer = ReplayDocumentAnalyzer()
    client = ReplayLlmClient()

    # 2. When directory exists, replay_dir resolves
    assert analyzer.replay_dir.exists()
    assert client.replay_dir.exists()

    # 3. When REPLAY_FIXTURES_DIR points to missing directory, raises clear FileNotFoundError
    monkeypatch.setattr(settings, "REPLAY_FIXTURES_DIR", "/nonexistent/replay/fixtures/dir")
    with pytest.raises(FileNotFoundError, match="Configured REPLAY_FIXTURES_DIR does not exist"):
        _ = analyzer.replay_dir

    with pytest.raises(FileNotFoundError, match="Configured REPLAY_FIXTURES_DIR does not exist"):
        _ = client.replay_dir
