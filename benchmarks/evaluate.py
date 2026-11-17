from __future__ import annotations

import argparse
import json
from pathlib import Path


def precision_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    return len(set(ranked_ids[:k]) & relevant_ids) / k


def dcg(relevances: list[int]) -> float:
    return sum((2**relevance - 1) / math_log2(index + 1) for index, relevance in enumerate(relevances, start=1))


def math_log2(value: float) -> float:
    import math

    return math.log2(value)


def ndcg_at_k(ranked_ids: list[str], relevance: dict[str, int], k: int) -> float:
    ideal = sorted(relevance.values(), reverse=True)[:k]
    actual = [relevance.get(doc_id, 0) for doc_id in ranked_ids[:k]]
    ideal_dcg = dcg(ideal)
    return dcg(actual) / ideal_dcg if ideal_dcg > 0 else 0.0


def evaluate(ranked: dict[str, list[str]], judged: dict[str, dict[str, list[str]]], k: int) -> dict[str, float]:
    precision_values = []
    ndcg_values = []
    for query, query_judgments in judged.items():
        relevant = set(query_judgments["relevant"])
        graded = {doc_id: 1 for doc_id in relevant}
        ranked_ids = ranked.get(query, [])
        precision_values.append(precision_at_k(ranked_ids, relevant, k))
        ndcg_values.append(ndcg_at_k(ranked_ids, graded, k))
    return {
        f"precision_at_{k}": sum(precision_values) / len(precision_values) if precision_values else 0.0,
        f"ndcg_at_{k}": sum(ndcg_values) / len(ndcg_values) if ndcg_values else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate search results against manually judged queries")
    parser.add_argument("--judgments", default="benchmarks/judged_queries.json")
    parser.add_argument("--ranked", required=True, help="JSON mapping queries to ranked document IDs")
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()
    judged = json.loads(Path(args.judgments).read_text(encoding="utf-8"))
    ranked = json.loads(Path(args.ranked).read_text(encoding="utf-8"))
    print(json.dumps(evaluate(ranked, judged, args.k), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
