from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

DEFAULT_K1 = 1.2
DEFAULT_B = 0.75


def safe_idf(total_documents: int, document_frequency: int) -> float:
    if total_documents < 1:
        return 0.0
    if document_frequency < 0 or document_frequency > total_documents:
        raise ValueError("document_frequency must be between zero and total_documents")
    return math.log(1.0 + (total_documents - document_frequency + 0.5) / (document_frequency + 0.5))


def bm25_tf_component(
    term_frequency: float,
    document_length: int,
    average_document_length: float,
    k1: float = DEFAULT_K1,
    b: float = DEFAULT_B,
) -> float:
    if term_frequency < 0:
        raise ValueError("term_frequency must not be negative")
    if document_length < 0:
        raise ValueError("document_length must not be negative")
    if average_document_length <= 0:
        return 0.0
    if k1 < 0:
        raise ValueError("k1 must not be negative")
    if not 0 <= b <= 1:
        raise ValueError("b must be between zero and one")
    denominator = term_frequency + k1 * (1.0 - b + b * document_length / average_document_length)
    if denominator == 0:
        return 0.0
    return term_frequency * (k1 + 1.0) / denominator


def bm25_score(
    query_terms: Sequence[str],
    postings: Mapping[str, Mapping[str, int]],
    document_lengths: Mapping[str, int],
    total_documents: int,
    average_document_length: float,
    idf_values: Mapping[str, float] | None = None,
    k1: float = DEFAULT_K1,
    b: float = DEFAULT_B,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for term in dict.fromkeys(query_terms):
        term_postings = postings.get(term, {})
        if idf_values is not None and term in idf_values:
            idf = float(idf_values[term])
            if not math.isfinite(idf) or idf < 0:
                idf = 0.0
        else:
            idf = safe_idf(total_documents, len(term_postings))
        for doc_id, term_frequency in term_postings.items():
            if doc_id not in document_lengths:
                raise KeyError(f"missing document length for {doc_id}")
            component = bm25_tf_component(
                term_frequency,
                document_lengths[doc_id],
                average_document_length,
                k1,
                b,
            )
            scores[doc_id] = scores.get(doc_id, 0.0) + idf * component
    return scores
