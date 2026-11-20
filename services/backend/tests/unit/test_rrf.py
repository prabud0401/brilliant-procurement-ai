"""Unit tests for Reciprocal Rank Fusion (RRF)."""

from __future__ import annotations

from collections import defaultdict

import pytest


def compute_rrf_score(
    vec_ranks: dict[str, int], fts_ranks: dict[str, int], k: float = 60.0
) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for doc_id, rank in vec_ranks.items():
        scores[doc_id] += 1.0 / (k + rank)
    for doc_id, rank in fts_ranks.items():
        scores[doc_id] += 1.0 / (k + rank)
    return dict(scores)


@pytest.mark.unit
def test_rrf_both_rankings_higher_than_single() -> None:
    # doc A is rank 1 in both vector and FTS
    # doc B is rank 1 in vector only
    # doc C is rank 1 in FTS only
    vec_ranks = {"doc_a": 1, "doc_b": 1, "doc_d": 2}
    fts_ranks = {"doc_a": 1, "doc_c": 1, "doc_d": 3}

    scores = compute_rrf_score(vec_ranks, fts_ranks, k=60.0)

    # doc_a: 1/61 + 1/61 = 2/61 ≈ 0.0328
    # doc_b: 1/61 ≈ 0.0164
    # doc_c: 1/61 ≈ 0.0164
    # doc_d: 1/62 + 1/63 ≈ 0.0320
    assert scores["doc_a"] > scores["doc_b"]
    assert scores["doc_a"] > scores["doc_c"]
    assert scores["doc_a"] > scores["doc_d"]
    assert scores["doc_d"] > scores["doc_b"]
    assert abs(scores["doc_a"] - (2.0 / 61.0)) < 1e-5


@pytest.mark.unit
def test_rrf_ranking_order() -> None:
    vec_ranks = {"doc_1": 1, "doc_2": 2, "doc_3": 5}
    fts_ranks = {"doc_1": 2, "doc_2": 1, "doc_3": 10}

    scores = compute_rrf_score(vec_ranks, fts_ranks, k=60.0)
    sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # doc_1 and doc_2 both have ranks 1 and 2, so equal scores
    assert abs(scores["doc_1"] - scores["doc_2"]) < 1e-5
    # doc_3 is far behind
    assert sorted_docs[2][0] == "doc_3"
    assert sorted_docs[0][1] > sorted_docs[2][1]
