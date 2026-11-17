from __future__ import annotations

import math

from search_service.bm25 import bm25_score, bm25_tf_component, safe_idf
from search_service.hybrid_ranker import hybrid_score, rank_candidates


def test_safe_idf_is_finite() -> None:
    assert math.isfinite(safe_idf(10, 0))
    assert math.isfinite(safe_idf(10, 10))


def test_bm25_tf_component_uses_configured_parameters() -> None:
    value = bm25_tf_component(3, 20, 10, k1=1.2, b=0.75)
    expected = 3 * 2.2 / (3 + 1.2 * (0.25 + 0.75 * 2))
    assert value == expected


def test_bm25_aggregates_matching_terms() -> None:
    scores = bm25_score(
        ["april", "month"],
        {"april": {"1": 1}, "month": {"1": 2}},
        {"1": 10},
        2,
        10.0,
    )
    assert scores["1"] > 0


def test_hybrid_formula_uses_candidate_set_maxima() -> None:
    score, normalized_bm25, normalized_pagerank = hybrid_score(5.0, 0.2, 10.0, 0.4)
    assert normalized_bm25 == 0.5
    assert normalized_pagerank == 0.5
    assert score == 0.5


def test_hybrid_handles_zero_denominators() -> None:
    score, normalized_bm25, normalized_pagerank = hybrid_score(0.0, 0.0, 0.0, 0.0)
    assert score == 0.0
    assert normalized_bm25 == 0.0
    assert normalized_pagerank == 0.0


def test_hybrid_ranking_is_deterministic() -> None:
    ranked = rank_candidates({"b": 4.0, "a": 4.0}, {"a": 0.2, "b": 0.1})
    assert [item.doc_id for item in ranked] == ["a", "b"]
