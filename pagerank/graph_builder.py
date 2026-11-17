"""Distributed link graph construction for PageRank."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LinkGraph:
    vertices: Any
    edges: Any


def build_graph(documents: Any) -> LinkGraph:
    from pyspark.sql.functions import col, explode, min

    vertices = documents.select("doc_id").where(col("doc_id").isNotNull()).distinct()
    id_references = vertices.select(
        col("doc_id").alias("reference"),
        col("doc_id").alias("destination"),
    )
    url_references = None
    if "url" in documents.columns:
        url_references = (
            documents.select(col("url").alias("reference"), col("doc_id").alias("destination"))
            .where(col("reference").isNotNull() & col("destination").isNotNull())
            .groupBy("reference")
            .agg(min("destination").alias("destination"))
            .join(
                vertices.select(col("doc_id").alias("reference")),
                "reference",
                "left_anti",
            )
        )
    exploded = (
        documents.select("doc_id", explode(col("links")).alias("reference"))
        .where(col("doc_id").isNotNull() & col("reference").isNotNull())
        .distinct()
    )
    by_id = exploded.join(id_references, "reference").select(
        col("doc_id").alias("src"),
        col("destination").alias("dst"),
    )
    candidates = by_id
    if url_references is not None:
        by_url = exploded.join(url_references, "reference").select(
            col("doc_id").alias("src"),
            col("destination").alias("dst"),
        )
        candidates = by_id.union(by_url)
    return LinkGraph(vertices, candidates.distinct())


def main() -> int:
    import argparse
    import json

    from config.settings import load_config, load_settings
    from ingestion.iceberg_writer import IcebergWriter, create_spark_session

    parser = argparse.ArgumentParser(description="Build a distributed PageRank link graph")
    parser.add_argument("--documents", default=None, help="Local or HDFS documents parquet path")
    parser.add_argument("--vertices-output", required=True, help="Vertices parquet output path")
    parser.add_argument("--edges-output", required=True, help="Edges parquet output path")
    parser.add_argument("--config", default=None)
    parser.add_argument("--settings", default=None)
    args = parser.parse_args()
    cluster = load_config(args.config)
    spark = create_spark_session(cluster, load_settings(args.settings), "dse-graph-builder")
    try:
        if args.documents:
            documents = spark.read.parquet(args.documents)
        else:
            writer = IcebergWriter(spark, cluster)
            writer.ensure_tables()
            documents = spark.table(writer.documents_table).filter("deleted = false")
        graph = build_graph(documents)
        graph.vertices.write.mode("overwrite").parquet(args.vertices_output)
        graph.edges.write.mode("overwrite").parquet(args.edges_output)
        print(json.dumps({"vertices": graph.vertices.count(), "edges": graph.edges.count()}, sort_keys=True))
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
