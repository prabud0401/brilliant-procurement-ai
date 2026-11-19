"""Response cache keyed by file sha256 and prompt version (NFR-COST-03)."""

from __future__ import annotations

import logging
from typing import Any

from app.ai.schemas import ExtractionResult

logger = logging.getLogger("ai.cache")

# In-memory cache for prompt version + sha256
_EXTRACTION_CACHE: dict[str, tuple[ExtractionResult, dict[str, Any]]] = {}


def make_cache_key(file_sha256: str, prompt_version: str) -> str:
    return f"{file_sha256}:{prompt_version}"


def get_cached_extraction(
    file_sha256: str, prompt_version: str = "prompts/extract_v1.md"
) -> tuple[ExtractionResult, dict[str, Any]] | None:
    key = make_cache_key(file_sha256, prompt_version)
    if key in _EXTRACTION_CACHE:
        logger.info("Extraction cache hit for key %s", key)
        return _EXTRACTION_CACHE[key]
    return None


def store_cached_extraction(
    file_sha256: str,
    prompt_version: str,
    result: ExtractionResult,
    metadata: dict[str, Any],
) -> None:
    key = make_cache_key(file_sha256, prompt_version)
    _EXTRACTION_CACHE[key] = (result, metadata)


def clear_cache() -> None:
    _EXTRACTION_CACHE.clear()
