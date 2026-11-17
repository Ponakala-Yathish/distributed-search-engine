"""Document length, term frequency, and average length statistics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from indexing.tokenizer import tokenize_dataframe


@dataclass(frozen=True)
class DocumentStatistics:
    documents: Any
    document_frequencies: Any
    summary: Any


def calculate_document_lengths(
    documents: Any,
    text_column: str = "text",
    output_column: str = "document_length",
) -> Any:
    from pyspark.sql.functions import size

    tokenized = tokenize_dataframe(documents, text_column, "__tokens")
    return tokenized.withColumn(output_column, size(tokenized["__tokens"])).drop("__tokens")


def calculate_document_frequencies(
    documents: Any,
    tokens_column: str = "tokens",
    output_column: str = "df",
) -> Any:
    from pyspark.sql.functions import col, explode

    if tokens_column not in documents.columns:
        tokenized = tokenize_dataframe(documents)
        tokens_column = "tokens"
    else:
        tokenized = documents
    return (
        tokenized.select("doc_id", explode(col(tokens_column)).alias("term"))
        .groupBy("term")
        .agg((col("doc_id").countDistinct()).cast("long").alias(output_column))
    )


def calculate_average_document_length(documents: Any, length_column: str = "document_length") -> Any:
    from pyspark.sql.functions import avg, count, lit

    return documents.agg(
        count(lit(1)).cast("long").alias("total_documents"),
        avg(lit(1) * 0 + col_value(documents, length_column)).cast("double").alias("avg_document_length"),
    )


def col_value(frame: Any, name: str) -> Any:
    from pyspark.sql.functions import col

    return col(name)


def compute_document_statistics(
    documents: Any,
    text_column: str = "text",
    length_column: str = "document_length",
) -> DocumentStatistics:
    lengths = calculate_document_lengths(documents, text_column, length_column)
    frequencies = calculate_document_frequencies(lengths)
    summary = calculate_average_document_length(lengths, length_column)
    return DocumentStatistics(lengths, frequencies, summary)


def main() -> int:
    import argparse
    import json

    from config.settings import load_config, load_settings
    from ingestion.iceberg_writer import IcebergWriter, create_spark_session

    parser = argparse.ArgumentParser(description="Compute document statistics from Iceberg documents")
    parser.add_argument("--config", default=None)
    parser.add_argument("--settings", default=None)
    args = parser.parse_args()
    cluster = load_config(args.config)
    spark = create_spark_session(cluster, load_settings(args.settings), "dse-document-statistics")
    try:
        writer = IcebergWriter(spark, cluster)
        writer.ensure_tables()
        documents = spark.table(writer.documents_table).filter("deleted = false")
        statistics = compute_document_statistics(documents)
        summary = statistics.summary.first()
        print(json.dumps(summary.asDict(), sort_keys=True))
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
