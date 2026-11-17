from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any

from search_service.bm25 import bm25_score
from search_service.hybrid_ranker import rank_candidates
from search_service.index_loader import IndexSnapshot, load_index
from search_service.tokenizer import preprocess_query


def percentile(values: list[float], percentage: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil((percentage / 100.0) * len(ordered)) - 1))
    return ordered[index]


def inverted_search(snapshot: IndexSnapshot, query: str, page_size: int) -> list[dict[str, Any]]:
    terms = preprocess_query(query)
    scores = bm25_score(
        terms,
        snapshot.postings,
        snapshot.doc_lengths,
        snapshot.total_documents,
        snapshot.avg_document_length,
        {term: stats.idf for term, stats in snapshot.terms.items()},
        snapshot.bm25["k1"],
        snapshot.bm25["b"],
    )
    ranked = rank_candidates(scores, snapshot.pagerank_scores)
    results = []
    for item in ranked[:page_size]:
        document = snapshot.documents[item.doc_id]
        results.append(
            {
                "document_id": item.doc_id,
                "title": document.title,
                "bm25_score": item.bm25_score,
                "final_score": item.score,
            }
        )
    return results


def naive_search(snapshot: IndexSnapshot, query: str, page_size: int) -> list[dict[str, Any]]:
    query_terms = set(preprocess_query(query))
    scored = []
    for document in snapshot.documents.values():
        document_terms = preprocess_query(document.text)
        if not query_terms:
            continue
        overlap = sum(1 for term in query_terms if term in document_terms)
        if overlap == 0:
            continue
        scored.append(
            {
                "document_id": document.doc_id,
                "title": document.title,
                "bm25_score": float(overlap),
                "final_score": float(overlap),
            }
        )
    scored.sort(key=lambda item: (-item["final_score"], item["document_id"]))
    return scored[:page_size]


def measure(operation: Any, queries: list[str], iterations: int, page_size: int) -> dict[str, Any]:
    durations = []
    result_count = 0
    for _ in range(iterations):
        for query in queries:
            started = time.perf_counter()
            result = operation(query, page_size)
            durations.append((time.perf_counter() - started) * 1000.0)
            result_count = len(result)
    return {
        "iterations": iterations,
        "queries": len(queries),
        "result_count": result_count,
        "mean_ms": statistics.fmean(durations) if durations else 0.0,
        "p50_ms": percentile(durations, 50),
        "p95_ms": percentile(durations, 95),
        "p99_ms": percentile(durations, 99),
        "throughput_qps": 1000.0 / (statistics.fmean(durations) if durations else 1.0),
    }


def run(index_path: str | Path, queries: list[str], iterations: int, page_size: int) -> dict[str, Any]:
    snapshot = load_index(index_path)
    return {
        "index_version": snapshot.version,
        "document_count": snapshot.document_count,
        "inverted_index": measure(
            lambda query, size: inverted_search(snapshot, query, size),
            queries,
            iterations,
            page_size,
        ),
        "naive_scan": measure(
            lambda query, size: naive_search(snapshot, query, size),
            queries,
            iterations,
            page_size,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure search latency and retrieval strategies")
    parser.add_argument("--index", required=True, help="validated serving index directory")
    parser.add_argument("--queries", default="april,august,history,science")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    queries = [query.strip() for query in args.queries.split(",") if query.strip()]
    result = run(args.index, queries, args.iterations, args.page_size)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
