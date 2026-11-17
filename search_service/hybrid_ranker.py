from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_BM25_WEIGHT = 0.7
DEFAULT_PAGERANK_WEIGHT = 0.3


@dataclass(frozen=True)
class HybridScore:
    doc_id: str
    score: float
    bm25_score: float
    pagerank: float
    bm25_normalized: float
    pagerank_normalized: float


def hybrid_score(
    bm25_score: float,
    pagerank: float,
    max_bm25: float,
    max_pagerank: float,
    bm25_weight: float = DEFAULT_BM25_WEIGHT,
    pagerank_weight: float = DEFAULT_PAGERANK_WEIGHT,
) -> tuple[float, float, float]:
    if bm25_weight < 0 or pagerank_weight < 0:
        raise ValueError("ranking weights must not be negative")
    if bm25_weight + pagerank_weight <= 0:
        raise ValueError("at least one ranking weight must be positive")
    normalized_bm25 = bm25_score / max_bm25 if max_bm25 > 0 else 0.0
    normalized_pagerank = pagerank / max_pagerank if max_pagerank > 0 else 0.0
    score = bm25_weight * normalized_bm25 + pagerank_weight * normalized_pagerank
    return score, normalized_bm25, normalized_pagerank


def rank_candidates(
    bm25_scores: Mapping[str, float],
    pagerank_scores: Mapping[str, float],
    bm25_weight: float = DEFAULT_BM25_WEIGHT,
    pagerank_weight: float = DEFAULT_PAGERANK_WEIGHT,
) -> list[HybridScore]:
    if not bm25_scores:
        return []
    max_bm25 = max(float(value) for value in bm25_scores.values())
    max_pagerank = max(float(pagerank_scores.get(doc_id, 0.0)) for doc_id in bm25_scores)
    ranked: list[HybridScore] = []
    for doc_id in bm25_scores:
        bm25_value = float(bm25_scores[doc_id])
        pagerank_value = float(pagerank_scores.get(doc_id, 0.0))
        if not math.isfinite(bm25_value) or not math.isfinite(pagerank_value):
            raise ValueError(f"non-finite ranking score for {doc_id}")
        score, normalized_bm25, normalized_pagerank = hybrid_score(
            bm25_value,
            pagerank_value,
            max_bm25,
            max_pagerank,
            bm25_weight,
            pagerank_weight,
        )
        ranked.append(
            HybridScore(
                doc_id=doc_id,
                score=score,
                bm25_score=bm25_value,
                pagerank=pagerank_value,
                bm25_normalized=normalized_bm25,
                pagerank_normalized=normalized_pagerank,
            )
        )
    ranked.sort(key=lambda item: (-item.score, item.doc_id))
    return ranked
