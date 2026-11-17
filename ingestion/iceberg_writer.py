"""Apache Iceberg catalog, schema, and MERGE support for ingestion."""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timezone
from typing import Any

from config.settings import load_config, load_settings


def _quote_identifier(identifier: str) -> str:
    return "`" + identifier.replace("`", "``") + "`"


def _qualified_table(catalog: str, table: str) -> str:
    table_name = table.split(".", 1)[1] if "." in table else table
    return f"{catalog}.{table_name}"


def _split_table(table: str) -> tuple[str, str]:
    if "." not in table:
        raise ValueError(f"table must include a catalog name: {table}")
    catalog, name = table.split(".", 1)
    return catalog, name


def create_spark_session(
    config: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    app_name: str = "distributed-search-engine",
) -> Any:
    from pyspark.sql import SparkSession

    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    cluster = config if config is not None else load_config()
    spark_settings = settings if settings is not None else load_settings()
    builder = SparkSession.builder.appName(app_name)
    master_url = cluster.get("services", {}).get("spark", {}).get("master_url")
    if master_url:
        builder = builder.master(str(master_url))
    driver_memory = spark_settings.get("spark", {}).get("driver_memory")
    executor_memory = spark_settings.get("spark", {}).get("executor_memory")
    executor_cores = spark_settings.get("spark", {}).get("executor_cores")
    shuffle_partitions = spark_settings.get("spark", {}).get("shuffle_partitions")
    parallelism = spark_settings.get("spark", {}).get("default_parallelism")
    serializer = spark_settings.get("spark", {}).get("serializer")
    if driver_memory:
        builder = builder.config("spark.driver.memory", str(driver_memory))
    if executor_memory:
        builder = builder.config("spark.executor.memory", str(executor_memory))
    if executor_cores:
        builder = builder.config("spark.executor.cores", str(executor_cores))
    if shuffle_partitions:
        builder = builder.config("spark.sql.shuffle.partitions", str(shuffle_partitions))
    if parallelism:
        builder = builder.config("spark.default.parallelism", str(parallelism))
    if serializer:
        builder = builder.config("spark.serializer", str(serializer))
    extensions = spark_settings.get("iceberg", {}).get("spark_extensions", [])
    if extensions:
        builder = builder.config("spark.sql.extensions", ",".join(str(item) for item in extensions))
    iceberg = cluster.get("iceberg", {})
    catalog = str(iceberg.get("catalog", "dse"))
    warehouse = iceberg.get("warehouse") or cluster.get("paths", {}).get("hdfs", {}).get("iceberg_warehouse")
    if not warehouse:
        raise ValueError("Iceberg warehouse is not configured")
    builder = builder.config(f"spark.sql.catalog.{catalog}", "org.apache.iceberg.spark.SparkCatalog")
    builder = builder.config(f"spark.sql.catalog.{catalog}.type", "hadoop")
    builder = builder.config(f"spark.sql.catalog.{catalog}.warehouse", str(warehouse))
    session = builder.getOrCreate()
    checkpoint_dir = cluster.get("paths", {}).get("hdfs", {}).get("serving")
    if checkpoint_dir:
        session.sparkContext.setCheckpointDir(f"{str(checkpoint_dir).rstrip('/')}/_spark_checkpoints")
    return session


class IcebergWriter:
    def __init__(self, spark: Any, config: dict[str, Any] | None = None) -> None:
        self.spark = spark
        self.config = config if config is not None else load_config()
        iceberg = self.config.get("iceberg", {})
        self.catalog = str(iceberg.get("catalog", "dse"))
        documents = str(iceberg.get("documents_table", "dse.documents"))
        rejections = str(iceberg.get("rejections_table", "dse.ingestion_rejections"))
        runs = str(iceberg.get("runs_table", "dse.ingestion_runs"))
        self.documents_table = _qualified_table(self.catalog, documents)
        self.rejections_table = _qualified_table(self.catalog, rejections)
        self.runs_table = _qualified_table(self.catalog, runs)
        _, self.documents_name = _split_table(self.documents_table)
        _, self.rejections_name = _split_table(self.rejections_table)
        _, self.runs_name = _split_table(self.runs_table)

    def ensure_tables(self) -> None:
        from pyspark.sql.types import ArrayType, BooleanType, DoubleType, LongType, StringType

        self.spark.sql(
            f"""
            CREATE TABLE IF NOT EXISTS {_quote_identifier(self.catalog)}.{_quote_identifier(self.documents_name)} (
                doc_id STRING,
                title STRING,
                url STRING,
                text STRING,
                links ARRAY<STRING>,
                version LONG,
                phase STRING,
                deleted BOOLEAN,
                ingested_at TIMESTAMP
            ) USING iceberg
            PARTITIONED BY (phase)
            """.strip()
        )
        self.spark.sql(
            f"""
            CREATE TABLE IF NOT EXISTS {_quote_identifier(self.catalog)}.{_quote_identifier(self.rejections_name)} (
                line_number LONG,
                phase STRING,
                reason STRING,
                raw_line STRING,
                rejected_at TIMESTAMP
            ) USING iceberg
            PARTITIONED BY (phase)
            """.strip()
        )
        self.spark.sql(
            f"""
            CREATE TABLE IF NOT EXISTS {_quote_identifier(self.catalog)}.{_quote_identifier(self.runs_name)} (
                run_id STRING,
                phase STRING,
                source STRING,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                total LONG,
                valid LONG,
                invalid LONG,
                duplicates LONG,
                accepted LONG,
                rejected LONG,
                duration_seconds DOUBLE
            ) USING iceberg
            """.strip()
        )
        self._assert_schema(self.documents_table, "doc_id", StringType())
        self._assert_schema(self.documents_table, "links", ArrayType(StringType()))
        self._assert_schema(self.documents_table, "deleted", BooleanType())
        self._assert_schema(self.rejections_table, "line_number", LongType())
        self._assert_schema(self.runs_table, "duration_seconds", DoubleType())

    def _assert_schema(self, table: str, column: str, expected: Any) -> None:
        fields = {field.name: field.dataType for field in self.spark.table(table).schema.fields}
        if column not in fields:
            raise ValueError(f"table {table} is missing column {column}")
        if fields[column] != expected:
            raise ValueError(f"table {table} column {column} has type {fields[column]}, expected {expected}")

    def merge_documents(self, documents: Any) -> None:
        from pyspark.sql.functions import col, current_timestamp

        source_view = f"dse_merge_source_{hashlib.sha256(str(documents.__class__.__name__).encode()).hexdigest()[:12]}"
        source = (
            documents.select(
                "doc_id",
                "title",
                "url",
                "text",
                "links",
                "version",
                "phase",
                "deleted",
            )
            .where(col("doc_id").isNotNull())
            .withColumn("ingested_at", current_timestamp())
        )
        source.createOrReplaceTempView(source_view)
        target_catalog, target_table = _split_table(self.documents_table)
        target = f"{_quote_identifier(target_catalog)}.{_quote_identifier(target_table)}"
        self.spark.sql(
            f"""
            MERGE INTO {target} AS target
            USING {source_view} AS source
            ON target.doc_id = source.doc_id
            WHEN MATCHED AND source.deleted = true AND source.version >= target.version THEN UPDATE SET
                target.version = source.version,
                target.phase = source.phase,
                target.deleted = true,
                target.ingested_at = source.ingested_at
            WHEN MATCHED AND source.deleted = false AND source.version >= target.version THEN UPDATE SET
                target.title = source.title,
                target.url = source.url,
                target.text = source.text,
                target.links = source.links,
                target.version = source.version,
                target.phase = source.phase,
                target.deleted = false,
                target.ingested_at = source.ingested_at
            WHEN NOT MATCHED THEN INSERT (
                doc_id, title, url, text, links, version, phase, deleted, ingested_at
            ) VALUES (
                source.doc_id, source.title, source.url, source.text, source.links,
                source.version, source.phase, source.deleted, source.ingested_at
            )
            """.strip()
        )
        self.spark.catalog.dropTempView(source_view)

    def append_rejections(self, rejections: Any) -> None:
        from pyspark.sql.functions import current_timestamp

        if not rejections.rdd.isEmpty():
            rejections.select(
                "line_number",
                "phase",
                "reason",
                "raw_line",
            ).withColumn("rejected_at", current_timestamp()).writeTo(self.rejections_table).append()

    def record_run(
        self,
        run_id: str,
        phase: int | str,
        source: str,
        started_at: datetime,
        completed_at: datetime,
        total: int,
        valid: int,
        invalid: int,
        duplicates: int,
        accepted: int,
        rejected: int,
        duration_seconds: float,
    ) -> None:
        from pyspark.sql.types import DoubleType, LongType, StringType, StructField, StructType, TimestampType

        row = (
            run_id,
            str(phase),
            source,
            started_at,
            completed_at,
            int(total),
            int(valid),
            int(invalid),
            int(duplicates),
            int(accepted),
            int(rejected),
            float(duration_seconds),
        )
        schema = StructType(
            [
                StructField("run_id", StringType(), False),
                StructField("phase", StringType(), False),
                StructField("source", StringType(), True),
                StructField("started_at", TimestampType(), True),
                StructField("completed_at", TimestampType(), True),
                StructField("total", LongType(), False),
                StructField("valid", LongType(), False),
                StructField("invalid", LongType(), False),
                StructField("duplicates", LongType(), False),
                StructField("accepted", LongType(), False),
                StructField("rejected", LongType(), False),
                StructField("duration_seconds", DoubleType(), False),
            ]
        )
        frame = self.spark.createDataFrame([row], schema=schema)
        frame.writeTo(self.runs_table).append()


def make_run_id(source: str, phase: int | str, started_at: datetime) -> str:
    value = f"{source}|{phase}|{started_at.isoformat()}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Initialize the configured Iceberg ingestion tables")
    parser.add_argument("--config", default=None)
    parser.add_argument("--settings", default=None)
    args = parser.parse_args()
    spark = create_spark_session(load_config(args.config), load_settings(args.settings), "dse-iceberg-init")
    try:
        writer = IcebergWriter(spark, load_config(args.config))
        writer.ensure_tables()
        print(f"initialized={writer.documents_table},{writer.rejections_table},{writer.runs_table}")
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
