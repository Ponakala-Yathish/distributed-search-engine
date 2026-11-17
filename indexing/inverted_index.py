"""Distributed inverted index construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from indexing.tokenizer import tokenize_dataframe


@dataclass(frozen=True)
class InvertedIndex:
    documents: Any
    postings: Any
    terms: Any


def build_postings(documents: Any, tokens_column: str = "tokens") -> Any:
    from pyspark.sql.functions import col, count, explode, lit

    tokenized = documents if tokens_column in documents.columns else tokenize_dataframe(documents)
    actual_tokens_column = tokens_column if tokens_column in tokenized.columns else "tokens"
    return (
        tokenized.select("doc_id", explode(col(actual_tokens_column)).alias("term"))
        .groupBy("term", "doc_id")
        .agg(count(lit(1)).cast("long").alias("tf"))
    )


def build_terms(postings: Any, total_documents: int) -> Any:
    from pyspark.sql.functions import col, count, lit, log

    document_count = max(1, int(total_documents))
    frequencies = postings.groupBy("term").agg(count(lit(1)).cast("long").alias("df"))
    return frequencies.withColumn(
        "idf",
        log(
            lit(1.0)
            + (lit(float(document_count)) - col("df").cast("double") + lit(0.5))
            / (col("df").cast("double") + lit(0.5))
        ).cast("double"),
    )


def export_documents(documents: Any, length_column: str = "document_length") -> Any:
    required = ["doc_id", "title", "url", "text", "links"]
    selected = [column for column in required if column in documents.columns]
    if length_column in documents.columns:
        selected.append(length_column)
    return documents.select(*selected)


def build_inverted_index(documents: Any, total_documents: int | None = None) -> InvertedIndex:
    from indexing.document_statistics import calculate_document_lengths

    lengths = calculate_document_lengths(documents)
    postings = build_postings(lengths)
    document_total = total_documents if total_documents is not None else lengths.count()
    terms = build_terms(postings, document_total)
    return InvertedIndex(export_documents(lengths), postings, terms)


def main() -> int:
    import argparse
    import json

    from config.settings import load_config, load_settings
    from ingestion.iceberg_writer import IcebergWriter, create_spark_session

    parser = argparse.ArgumentParser(description="Build distributed postings and terms from Iceberg documents")
    parser.add_argument("--documents", default=None, help="Local or HDFS documents parquet path")
    parser.add_argument("--postings-output", required=True, help="Postings parquet output path")
    parser.add_argument("--terms-output", required=True, help="Terms parquet output path")
    parser.add_argument("--config", default=None)
    parser.add_argument("--settings", default=None)
    args = parser.parse_args()
    cluster = load_config(args.config)
    spark = create_spark_session(cluster, load_settings(args.settings), "dse-inverted-index")
    try:
        if args.documents:
            documents = spark.read.parquet(args.documents)
        else:
            writer = IcebergWriter(spark, cluster)
            writer.ensure_tables()
            documents = spark.table(writer.documents_table).filter("deleted = false")
        index = build_inverted_index(documents)
        index.postings.write.mode("overwrite").parquet(args.postings_output)
        index.terms.write.mode("overwrite").parquet(args.terms_output)
        print(
            json.dumps(
                {
                    "documents": index.documents.count(),
                    "postings": index.postings.count(),
                    "terms": index.terms.count(),
                },
                sort_keys=True,
            )
        )
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
