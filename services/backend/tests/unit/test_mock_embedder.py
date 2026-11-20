"""Unit tests for MockEmbedder (determinism, dimensions, semantic similarity)."""

from __future__ import annotations

import math

import pytest

from app.ai.providers.mock import MockEmbedder, compute_deterministic_embedding


def cosine_sim(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


@pytest.mark.unit
def test_mock_embedder_dimension_and_norm() -> None:
    embedder = MockEmbedder()
    vectors = embedder.embed(["Hello world", "Quotation Q-1042 Net 30"])
    assert len(vectors) == 2

    for v in vectors:
        assert len(v) == 1536
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) < 1e-4


@pytest.mark.unit
def test_mock_embedder_determinism() -> None:
    embedder = MockEmbedder()
    text = "Gulf Line IT Trading quote Q-1042 total AED 28,875.00"
    v1 = embedder.embed([text])[0]
    v2 = embedder.embed([text])[0]
    v3 = compute_deterministic_embedding(text)

    assert v1 == v2
    assert v1 == v3


@pytest.mark.unit
def test_mock_embedder_meaningful_similarity() -> None:
    embedder = MockEmbedder()
    text_it1 = "Laptop 14in Intel Core i7 16GB RAM"
    text_it2 = "Laptop 14 inch Core i7 computer notebook"
    text_construction = "Portland cement ready-mix concrete sand gravel"

    v_it1 = embedder.embed([text_it1])[0]
    v_it2 = embedder.embed([text_it2])[0]
    v_const = embedder.embed([text_construction])[0]

    sim_related = cosine_sim(v_it1, v_it2)
    sim_unrelated = cosine_sim(v_it1, v_const)

    assert sim_related > sim_unrelated
    assert sim_related > 0.15
