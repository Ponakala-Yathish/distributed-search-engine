"""Distributed Spark PageRank with explicit dangling-node handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PageRankResult:
    scores: Any
    iterations: int
    converged: bool
    delta: float


def calculate_pagerank(
    vertices: Any,
    edges: Any,
    damping: float = 0.85,
    iterations: int = 15,
    tolerance: float = 1e-6,
) -> PageRankResult:
    if not 0.0 < damping < 1.0:
        raise ValueError("damping must be between 0 and 1")
    if int(iterations) < 15:
        raise ValueError("PageRank iterations must be at least 15")
    if float(tolerance) <= 0.0:
        raise ValueError("tolerance must be positive")
    from pyspark.sql.functions import abs as spark_abs
    from pyspark.sql.functions import col, lit, when
    from pyspark.sql.functions import sum as spark_sum

    unique_vertices = vertices.select("doc_id").where(col("doc_id").isNotNull()).distinct().cache()
    unique_edges = (
        edges.select("src", "dst")
        .join(unique_vertices.select(col("doc_id").alias("src")), "src")
        .join(unique_vertices.select(col("doc_id").alias("dst")), "dst")
        .select("src", "dst")
        .distinct()
    )
    total = unique_vertices.count()
    if total == 0:
        empty = unique_vertices.withColumn("score", lit(0.0).cast("double"))
        unique_vertices.unpersist()
        return PageRankResult(empty, int(iterations), True, 0.0)
    current = unique_vertices.withColumn("score", lit(1.0 / total).cast("double")).cache()
    degrees = unique_edges.groupBy("src").agg(spark_sum(lit(1)).cast("long").alias("out_degree"))
    last_delta = float("inf")
    converged = False
    completed = 0
    maximum_iterations = max(15, int(iterations))
    while completed < maximum_iterations:
        outgoing = current.join(degrees, current["doc_id"] == degrees["src"], "left")
        dangling_sum = outgoing.where(col("out_degree").isNull()).agg(spark_sum("score").cast("double")).first()[0]
        dangling_mass = float(dangling_sum or 0.0)
        contributions = (
            unique_edges.join(degrees, "src")
            .join(current.select(current["doc_id"].alias("src"), current["score"].alias("src_score")), "src")
            .withColumn("contribution", col("src_score") / col("out_degree").cast("double"))
            .groupBy("dst")
            .agg(spark_sum("contribution").cast("double").alias("incoming"))
        )
        incoming = contributions.select("dst", "incoming")
        updated = (
            unique_vertices.join(incoming, unique_vertices["doc_id"] == incoming["dst"], "left")
            .select(
                unique_vertices["doc_id"].alias("doc_id"),
                (
                    lit((1.0 - damping) / total)
                    + lit(damping)
                    * (
                        lit(dangling_mass / total)
                        + when(col("incoming").isNull(), lit(0.0)).otherwise(col("incoming"))
                    )
                ).cast("double").alias("score"),
            )
        )
        delta_row = (
            updated.alias("updated")
            .join(current.alias("previous"), "doc_id")
            .select(spark_abs(col("updated.score") - col("previous.score")).alias("difference"))
            .agg(spark_sum("difference").cast("double").alias("delta"))
            .first()
        )
        last_delta = float(delta_row["delta"] or 0.0)
        current.unpersist()
        if current.sparkSession.sparkContext.getCheckpointDir():
            current = updated.checkpoint(eager=True)
        else:
            current = updated.localCheckpoint(eager=True)
        completed += 1
        if completed >= 15 and last_delta < float(tolerance):
            converged = True
            break
    current = current.select("doc_id", col("score").cast("double").alias("score"))
    unique_vertices.unpersist()
    return PageRankResult(current, completed, converged, last_delta)


def save_pagerank(scores: Any, path: str) -> None:
    scores.select("doc_id", "score").write.mode("overwrite").parquet(path)


def main() -> int:
    import argparse
    import json

    from config.settings import load_config, load_settings
    from ingestion.iceberg_writer import IcebergWriter, create_spark_session
    from pagerank.graph_builder import build_graph

    parser = argparse.ArgumentParser(description="Compute distributed PageRank over a document link graph")
    parser.add_argument("--documents", default=None, help="Local or HDFS documents parquet path")
    parser.add_argument("--output", required=True, help="Final PageRank parquet output path")
    parser.add_argument("--damping", type=float, default=None)
    parser.add_argument("--iterations", type=int, default=None)
    parser.add_argument("--tolerance", type=float, default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--settings", default=None)
    args = parser.parse_args()
    cluster = load_config(args.config)
    ranking = cluster.get("ranking", {}).get("pagerank", {})
    damping = args.damping if args.damping is not None else float(ranking.get("damping", 0.85))
    iterations = args.iterations if args.iterations is not None else int(ranking.get("iterations", 15))
    tolerance = args.tolerance if args.tolerance is not None else float(ranking.get("tolerance", 1e-6))
    spark = create_spark_session(cluster, load_settings(args.settings), "dse-pagerank")
    try:
        if args.documents:
            documents = spark.read.parquet(args.documents)
        else:
            writer = IcebergWriter(spark, cluster)
            writer.ensure_tables()
            documents = spark.table(writer.documents_table).filter("deleted = false")
        graph = build_graph(documents)
        result = calculate_pagerank(graph.vertices, graph.edges, damping, iterations, tolerance)
        save_pagerank(result.scores, args.output)
        print(
            json.dumps(
                {
                    "iterations": result.iterations,
                    "converged": result.converged,
                    "delta": result.delta,
                },
                sort_keys=True,
            )
        )
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
