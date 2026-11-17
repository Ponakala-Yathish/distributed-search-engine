"""Phase-aware ingestion pipeline."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from config.settings import load_config, load_settings
from ingestion.deduplication import deduplicate_dataframe
from ingestion.iceberg_writer import IcebergWriter, create_spark_session, make_run_id, utc_now
from ingestion.parser import parse_jsonl_spark
from ingestion.validation import PHASE_DEFAULT_VERSIONS, validate_dataframe


def _hdfs_destination(config: dict[str, Any], phase: int, override: str | None) -> str:
    if override:
        return override
    datasets = config.get("datasets", {}).get(f"phase{phase}", {})
    filename = str(datasets.get("filename", "pages.jsonl" if phase == 0 else "changes.json"))
    root = str(config.get("paths", {}).get("hdfs", {}).get("datasets", "")).rstrip("/")
    if not root:
        raise ValueError("HDFS datasets path is not configured")
    return f"{root}/{filename}"


def _default_source(config: dict[str, Any], phase: int) -> str:
    datasets = config.get("datasets", {}).get(f"phase{phase}", {})
    configured = datasets.get("path")
    if configured:
        return str(configured)
    filename = str(datasets.get("filename", "pages.jsonl" if phase == 0 else "changes.json"))
    root = str(config.get("paths", {}).get("local", {}).get("dataset_root", "data/datasets"))
    return str(Path(root) / filename)


def _is_remote(path: str) -> bool:
    return urlparse(path).scheme in {"hdfs", "s3a", "gs", "abfs", "wasb"}


def _upload_to_hdfs(spark: Any, source: str, destination: str) -> None:
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"ingestion source does not exist: {source_path}")
    jvm = spark._jvm
    uri = destination
    parsed = urlparse(destination)
    if not parsed.scheme:
        raise ValueError(f"HDFS destination must be a URI: {destination}")
    fs = jvm.org.apache.hadoop.fs.FileSystem.get(uri, spark.sparkContext._jsc.hadoopConfiguration())
    parent = destination.rsplit("/", 1)[0]
    if parent:
        fs.mkdirs(parent, True)
    fs.copyFromLocalFile(False, True, str(source_path), destination)


def _filter_links(documents: Any, existing_documents: Any) -> Any:
    from pyspark.sql.functions import array, coalesce, col, collect_list, explode, lit, sort_array

    prepared = documents
    if "op" not in prepared.columns:
        prepared = prepared.withColumn("op", lit("UPSERT"))
    else:
        prepared = prepared.withColumn("op", coalesce(col("op"), lit("UPSERT")))
    if "deleted" not in prepared.columns:
        prepared = prepared.withColumn("deleted", lit(False))
    else:
        prepared = prepared.withColumn("deleted", coalesce(col("deleted"), lit(False)))
    upserts = prepared.filter((col("op") == "UPSERT") & (~col("deleted")))
    deletes = (
        prepared.filter((col("op") == "DELETE") | col("deleted"))
        .select(
            "doc_id",
            "version",
            "phase",
            "op",
            col("deleted").alias("deleted"),
        )
        .withColumn("deleted", lit(True))
        .distinct()
    )
    existing = existing_documents.filter(~coalesce(col("deleted"), lit(False))).join(
        deletes.select("doc_id").distinct(), "doc_id", "left_anti"
    )
    valid_ids = existing.select("doc_id").union(upserts.select("doc_id")).distinct()
    valid_urls = (
        existing.select(col("url").alias("url"))
        .union(upserts.select(col("url").alias("url")))
        .filter(col("url").isNotNull())
        .distinct()
    )
    references = valid_ids.select(col("doc_id").alias("reference")).union(
        valid_urls.select(col("url").alias("reference"))
    ).distinct()
    exploded = upserts.select("doc_id", explode(col("links")).alias("link"))
    filtered_links = exploded.join(references, exploded["link"] == references["reference"])
    filtered_links = filtered_links.groupBy("doc_id").agg(
        sort_array(collect_list("link")).alias("valid_links")
    )
    selected = upserts.select("doc_id", "title", "url", "text", "version", "phase", "op")
    selected = selected.join(filtered_links, "doc_id", "left").select(
        "doc_id",
        "title",
        "url",
        "text",
        coalesce(col("valid_links"), array().cast("array<string>")).alias("links"),
        "version",
        "phase",
        "op",
        lit(False).alias("deleted"),
    )
    delete_rows = deletes.select(
        "doc_id",
        lit(None).cast("string").alias("title"),
        lit(None).cast("string").alias("url"),
        lit(None).cast("string").alias("text"),
        lit(None).cast("array<string>").alias("links"),
        "version",
        "phase",
        "op",
        "deleted",
    )
    return selected.unionByName(delete_rows)


def run_ingestion(
    phase: int,
    source: str | None = None,
    upload: bool = False,
    hdfs_path: str | None = None,
    config: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    spark: Any | None = None,
) -> dict[str, Any]:
    if phase not in PHASE_DEFAULT_VERSIONS:
        raise ValueError("phase must be 0 or 1")
    cluster = config if config is not None else load_config()
    spark_settings = settings if settings is not None else load_settings()
    owns_spark = spark is None
    active_spark = (
        spark
        if spark is not None
        else create_spark_session(cluster, spark_settings, f"dse-ingestion-phase{phase}")
    )
    started_at = utc_now()
    source_path = source or _default_source(cluster, phase)
    remote_source = _is_remote(source_path)
    if upload:
        if remote_source:
            raise ValueError("--upload requires a local source")
        destination = _hdfs_destination(cluster, phase, hdfs_path)
        _upload_to_hdfs(active_spark, source_path, destination)
        source_path = destination
    writer = IcebergWriter(active_spark, cluster)
    writer.ensure_tables()
    parsed_records, parse_rejections = parse_jsonl_spark(active_spark, source_path, phase)
    parsed_records.cache()
    parse_rejections.cache()
    default_version = PHASE_DEFAULT_VERSIONS[phase]
    valid_records, validation_rejections = validate_dataframe(parsed_records, phase, default_version)
    valid_records.cache()
    validation_rejections.cache()
    total = parsed_records.count() + parse_rejections.count()
    valid_count = valid_records.count()
    invalid_count = total - valid_count
    deduplicated = deduplicate_dataframe(valid_records)
    deduplicated.cache()
    accepted_count = deduplicated.count()
    duplicates = valid_count - accepted_count
    existing_documents = active_spark.table(writer.documents_table)
    merged = _filter_links(deduplicated, existing_documents)
    rejects = parse_rejections.unionByName(validation_rejections).orderBy("line_number")
    writer.append_rejections(rejects)
    writer.merge_documents(merged)
    current_documents = active_spark.table(writer.documents_table)
    current_documents = current_documents.filter(~current_documents["deleted"])
    refreshed = _filter_links(current_documents, current_documents)
    writer.merge_documents(refreshed)
    completed_at = utc_now()
    duration = (completed_at - started_at).total_seconds()
    run_id = make_run_id(source_path, phase, started_at)
    writer.record_run(
        run_id=run_id,
        phase=phase,
        source=source_path,
        started_at=started_at,
        completed_at=completed_at,
        total=total,
        valid=valid_count,
        invalid=invalid_count,
        duplicates=duplicates,
        accepted=accepted_count,
        rejected=invalid_count,
        duration_seconds=duration,
    )
    summary = {
        "run_id": run_id,
        "phase": phase,
        "source": source_path,
        "total": total,
        "valid": valid_count,
        "invalid": invalid_count,
        "duplicates": duplicates,
        "accepted": accepted_count,
        "rejected": invalid_count,
        "duration_seconds": duration,
    }
    parsed_records.unpersist()
    parse_rejections.unpersist()
    valid_records.unpersist()
    validation_rejections.unpersist()
    deduplicated.unpersist()
    if owns_spark:
        active_spark.stop()
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the distributed search engine ingestion pipeline")
    parser.add_argument(
        "--phase",
        type=int,
        choices=(0, 1),
        required=True,
        help="Ingestion phase: 0 for pages or 1 for changes",
    )
    parser.add_argument("--source", default=None, help="Local or HDFS source path")
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload a local source to the configured HDFS datasets path",
    )
    parser.add_argument("--hdfs-path", default=None, help="Override the HDFS upload destination")
    parser.add_argument("--config", default=None, help="Cluster configuration YAML")
    parser.add_argument("--settings", default=None, help="Spark and ingestion settings YAML")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        summary = run_ingestion(
            phase=args.phase,
            source=args.source,
            upload=args.upload,
            hdfs_path=args.hdfs_path,
            config=load_config(args.config),
            settings=load_settings(args.settings),
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        traceback.print_exc()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
