"""Deterministic, version-aware document deduplication."""

from __future__ import annotations

import json
from typing import Any


def canonical_record(record: dict[str, Any]) -> str:
    normalized = {
        "doc_id": record.get("doc_id"),
        "url": record.get("url"),
        "title": record.get("title"),
        "text": record.get("text"),
        "links": sorted(record.get("links") or []),
        "version": record.get("version"),
        "phase": record.get("phase"),
        "op": record.get("op", "UPSERT"),
    }
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _is_better(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
    candidate_version = candidate.get("version")
    current_version = current.get("version")
    if isinstance(candidate_version, int) and isinstance(current_version, int) and candidate_version != current_version:
        return candidate_version > current_version
    candidate_phase = str(candidate.get("phase", ""))
    current_phase = str(current.get("phase", ""))
    if candidate_phase != current_phase:
        return candidate_phase > current_phase
    candidate_delete = candidate.get("op") == "DELETE"
    current_delete = current.get("op") == "DELETE"
    if candidate_delete != current_delete:
        return candidate_delete
    return canonical_record(candidate) < canonical_record(current)


def deduplicate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for record in records:
        doc_id = record.get("doc_id")
        if not isinstance(doc_id, str):
            continue
        if doc_id not in selected or _is_better(record, selected[doc_id]):
            selected[doc_id] = record
    return [selected[doc_id] for doc_id in sorted(selected)]


def deduplicate_dataframe(records: Any) -> Any:
    from pyspark.sql import Window
    from pyspark.sql.functions import array_sort, col, desc, lit, to_json, when

    canonical_parts = [
        col("doc_id"),
        col("url"),
        col("title"),
        col("text"),
        to_json(array_sort(col("links"))),
        col("version"),
        col("phase"),
        when(col("op") == "DELETE", lit(1)).otherwise(lit(0)),
    ]
    canonical = concat_parts(canonical_parts)
    delete_priority = when(col("op") == "DELETE", lit(1)).otherwise(lit(0))
    window = Window.partitionBy("doc_id").orderBy(
        desc("version"),
        desc("phase"),
        desc(delete_priority),
        asc(canonical),
    )
    ranked = records.withColumn("_canonical", canonical).withColumn("_delete_priority", delete_priority)
    ranked = ranked.withColumn("_rank", row_number().over(window))
    return ranked.filter(col("_rank") == 1).drop("_canonical", "_delete_priority", "_rank")


def concat_parts(parts: list[Any]) -> Any:
    from pyspark.sql.functions import concat_ws

    return concat_ws("\u001f", *[part for part in parts if part is not None])


def asc(column: Any) -> Any:
    from pyspark.sql.functions import asc as spark_asc

    return spark_asc(column)


def row_number() -> Any:
    from pyspark.sql.functions import row_number as spark_row_number

    return spark_row_number()


def main() -> int:
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Deduplicate JSONL records by document ID")
    parser.add_argument("source", help="Local JSONL file")
    args = parser.parse_args()
    records: list[dict[str, Any]] = []
    with Path(args.source).open(encoding="utf-8") as stream:
        for line in stream:
            value = json.loads(line)
            if isinstance(value, dict):
                records.append(value)
    result = deduplicate_records(records)
    print(f"input={len(records)} unique={len(result)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
