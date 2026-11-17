"""Validated, versioned search-index exports."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

METADATA_KEYS = {
    "version",
    "phase",
    "created_at",
    "document_count",
    "total_documents",
    "avg_document_length",
    "bm25",
    "pagerank",
    "files",
}
REQUIRED_FILES = (
    "metadata.json",
    "documents.parquet",
    "postings.parquet",
    "terms.parquet",
    "pagerank.parquet",
)


def versioned_directory(output_root: str | Path, version: int | str) -> Path:
    return Path(output_root) / f"index-v{version}"


def _write_parquet(frame: Any, path: str | Path) -> None:
    frame.write.mode("overwrite").option("compression", "zstd").parquet(str(path))


def _parquet_files(path: Path) -> list[Path]:
    return [item for item in path.rglob("*.parquet") if item.is_file() and item.stat().st_size > 0]


def validate_export(
    spark: Any,
    root: str | Path,
    data_root: str | Path | None = None,
) -> dict[str, Any]:
    export_root = Path(root)
    parquet_root = str(data_root) if data_root is not None else str(export_root)
    if not export_root.is_dir():
        raise ValueError(f"export directory does not exist: {export_root}")
    metadata_path = export_root / "metadata.json"
    if not metadata_path.is_file() or metadata_path.stat().st_size == 0:
        raise ValueError("metadata.json is missing or empty")
    with metadata_path.open(encoding="utf-8") as stream:
        metadata = cast(dict[str, Any], json.load(stream))
    if set(metadata) != METADATA_KEYS:
        raise ValueError(f"metadata keys must be exactly {sorted(METADATA_KEYS)}")
    files = metadata.get("files")
    if not isinstance(files, dict) or set(files) != set(REQUIRED_FILES) - {"metadata.json"}:
        raise ValueError("metadata files mapping is incomplete")
    expected_schemas = {
        "documents.parquet": {
            "doc_id": "string",
            "title": "string",
            "url": "string",
            "text": "string",
            "links": "array<string>",
                "document_length": "bigint",
            },
            "postings.parquet": {"term": "string", "doc_id": "string", "tf": "bigint"},
            "terms.parquet": {"term": "string", "df": "bigint", "idf": "double"},

        "pagerank.parquet": {"doc_id": "string", "pagerank": "double"},
    }
    for filename, expected in expected_schemas.items():
        target = f"{str(parquet_root).rstrip('/')}/{filename}"
        if data_root is None:
            target_path = Path(target)
            if not target_path.is_dir() or not _parquet_files(target_path):
                raise ValueError(f"{filename} is missing or has no nonempty parquet files")
        schema = {field.name: field.dataType.simpleString() for field in spark.read.parquet(target).schema.fields}
        if schema != expected:
            raise ValueError(f"{filename} schema is invalid: {schema}")
    documents = spark.read.parquet(f"{str(parquet_root).rstrip('/')}/documents.parquet")
    postings = spark.read.parquet(f"{str(parquet_root).rstrip('/')}/postings.parquet")
    terms = spark.read.parquet(f"{str(parquet_root).rstrip('/')}/terms.parquet")
    pagerank = spark.read.parquet(f"{str(parquet_root).rstrip('/')}/pagerank.parquet")
    document_rows = documents.collect()
    document_count = len(document_rows)
    document_ids = {str(row["doc_id"]) for row in document_rows}
    if len(document_ids) != document_count:
        raise ValueError("documents.parquet contains duplicate document IDs")
    if int(metadata["document_count"]) != document_count:
        raise ValueError("metadata document_count does not match documents.parquet")
    if int(metadata["total_documents"]) != document_count:
        raise ValueError("metadata total_documents does not match documents.parquet")
    computed_average = sum(int(row["document_length"]) for row in document_rows) / max(1, document_count)
    if abs(float(metadata["avg_document_length"]) - computed_average) > 1e-6:
        raise ValueError("metadata avg_document_length does not match documents.parquet")
    posting_counts: dict[str, int] = {}
    posting_pairs: set[tuple[str, str]] = set()
    for row in postings.collect():
        term = str(row["term"])
        doc_id = str(row["doc_id"])
        if doc_id not in document_ids:
            raise ValueError(f"postings references unknown document: {doc_id}")
        pair = (term, doc_id)
        if pair in posting_pairs:
            raise ValueError(f"duplicate posting for term {term} and document {doc_id}")
        posting_pairs.add(pair)
        posting_counts[term] = posting_counts.get(term, 0) + 1
    term_rows = terms.collect()
    term_ids = [str(row["term"]) for row in term_rows]
    if len(term_ids) != len(set(term_ids)):
        raise ValueError("terms.parquet contains duplicate terms")
    if set(term_ids) != set(posting_counts):
        raise ValueError("terms.parquet and postings.parquet contain different terms")
    for row in term_rows:
        term = str(row["term"])
        df = int(row["df"])
        if df != posting_counts[term]:
            raise ValueError(f"term {term} has df {df} but {posting_counts[term]} postings")
        expected_idf = float(
            math.log(1.0 + (document_count - df + 0.5) / (df + 0.5))
        )
        if abs(float(row["idf"]) - expected_idf) > 1e-9:
            raise ValueError(f"term {term} has an invalid idf")
    pagerank_ids = [str(row["doc_id"]) for row in pagerank.collect()]
    if len(pagerank_ids) != len(set(pagerank_ids)):
        raise ValueError("pagerank.parquet contains duplicate documents")
    if set(pagerank_ids) != document_ids:
        raise ValueError("pagerank.parquet does not contain exactly the exported documents")
    bm25 = metadata.get("bm25")
    if not isinstance(bm25, dict) or float(bm25.get("k1", -1.0)) < 0 or not 0 <= float(bm25.get("b", -1.0)) <= 1:
        raise ValueError("metadata bm25 values are invalid")
    return metadata


def export_index(
    spark: Any,
    documents: Any,
    postings: Any,
    terms: Any,
    pagerank: Any,
    output_root: str | Path,
    version: int | str,
    phase: int | str,
    bm25: dict[str, Any] | None = None,
    pagerank_config: dict[str, Any] | None = None,
    created_at: datetime | None = None,
    data_root: str | Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    output_path = Path(output_root)
    export_root = versioned_directory(output_path, version)
    if export_root.exists():
        raise ValueError(f"index version already exists and is immutable: {export_root}")
    output_path.mkdir(parents=True, exist_ok=True)
    temporary_root = output_path / f".index-v{version}-{uuid.uuid4().hex}.tmp"
    from pyspark.sql.functions import col

    document_export = documents.select(
        "doc_id",
        "title",
        "url",
        "text",
        "links",
        col("document_length").cast("long").alias("document_length"),
    )
    postings_export = postings.select("term", "doc_id", "tf")
    terms_export = terms.select("term", "df", "idf")
    pagerank_export = pagerank.select("doc_id", pagerank["score"].alias("pagerank"))
    parquet_root = str(data_root).rstrip("/") if data_root is not None else str(temporary_root)
    _write_parquet(document_export, f"{parquet_root}/documents.parquet")
    _write_parquet(postings_export, f"{parquet_root}/postings.parquet")
    _write_parquet(terms_export, f"{parquet_root}/terms.parquet")
    _write_parquet(pagerank_export, f"{parquet_root}/pagerank.parquet")
    from pyspark.sql.functions import avg, count, lit

    summary = documents.agg(
        count(lit(1)).cast("long").alias("document_count"),
        avg(col("document_length")).cast("double").alias("avg_document_length"),
    ).first()
    timestamp = created_at or datetime.now(timezone.utc)
    metadata = {
        "version": int(version),
        "phase": str(phase),
        "created_at": timestamp.astimezone(timezone.utc).isoformat(),
        "document_count": int(summary["document_count"]),
        "total_documents": int(summary["document_count"]),
        "avg_document_length": float(summary["avg_document_length"] or 0.0),
        "bm25": {
            "k1": float((bm25 or {}).get("k1", 1.2)),
            "b": float((bm25 or {}).get("b", 0.75)),
        },
        "pagerank": {
            "damping": float((pagerank_config or {}).get("damping", 0.85)),
            "iterations": int((pagerank_config or {}).get("iterations", 15)),
            "tolerance": float((pagerank_config or {}).get("tolerance", 1e-6)),
        },
        "files": {
            "documents.parquet": "documents.parquet",
            "postings.parquet": "postings.parquet",
            "terms.parquet": "terms.parquet",
            "pagerank.parquet": "pagerank.parquet",
        },
    }
    metadata_path = temporary_root / "metadata.json"
    with metadata_path.open("w", encoding="utf-8") as stream:
        json.dump(metadata, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    try:
        validate_export(spark, temporary_root, data_root=data_root)
        temporary_root.rename(export_root)
    except Exception:
        shutil.rmtree(temporary_root, ignore_errors=True)
        raise
    return export_root, metadata


def main() -> int:
    from config.settings import load_config, load_settings
    from indexing.inverted_index import build_inverted_index
    from ingestion.iceberg_writer import IcebergWriter, create_spark_session
    from pagerank.algorithm import calculate_pagerank
    from pagerank.graph_builder import build_graph

    parser = argparse.ArgumentParser(description="Build and export a validated versioned search index")
    parser.add_argument("--output-root", required=True, help="Local directory containing the versioned export")
    parser.add_argument("--data-root", default=None, help="Optional shared filesystem root for parquet data")
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--phase", type=int, choices=(0, 1), required=True)
    parser.add_argument("--documents", default=None, help="Local or HDFS documents parquet path")
    parser.add_argument("--config", default=None)
    parser.add_argument("--settings", default=None)
    args = parser.parse_args()
    try:
        cluster = load_config(args.config)
        spark = create_spark_session(cluster, load_settings(args.settings), "dse-index-export")
        try:
            if args.documents:
                documents = spark.read.parquet(args.documents)
            else:
                writer = IcebergWriter(spark, cluster)
                writer.ensure_tables()
                documents = spark.table(writer.documents_table).filter("deleted = false")
            index = build_inverted_index(documents)
            graph = build_graph(index.documents)
            ranking_config = cluster.get("ranking", {}).get("pagerank", {})
            rank = calculate_pagerank(
                graph.vertices,
                graph.edges,
                damping=float(ranking_config.get("damping", 0.85)),
                iterations=int(ranking_config.get("iterations", 15)),
                tolerance=float(ranking_config.get("tolerance", 1e-6)),
            )
            path, metadata = export_index(
                spark=spark,
                documents=index.documents,
                postings=index.postings,
                terms=index.terms,
                pagerank=rank.scores,
                output_root=args.output_root,
                version=args.version,
                phase=args.phase,
                bm25=cluster.get("ranking", {}).get("bm25", {}),
                pagerank_config=ranking_config,
                data_root=args.data_root,
            )
            print(json.dumps({"path": str(path), "metadata": metadata}, indent=2, sort_keys=True))
        finally:
            spark.stop()
        return 0
    except Exception as exc:
        traceback.print_exc()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
