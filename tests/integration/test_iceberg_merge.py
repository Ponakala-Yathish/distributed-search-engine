from __future__ import annotations

import os
from pathlib import Path

import pytest


def _iceberg_runtime() -> str | None:
    value = os.getenv("DSE_TEST_ICEBERG_JAR")
    return value if value and Path(value).is_file() else None


@pytest.fixture(scope="module")
def iceberg_spark(tmp_path_factory):
    runtime = _iceberg_runtime()
    if runtime is None:
        pytest.skip("DSE_TEST_ICEBERG_JAR is not configured")
    import sys

    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

    from pyspark.sql import SparkSession

    warehouse = tmp_path_factory.mktemp("iceberg-warehouse").as_uri()
    session = (
        SparkSession.builder.master("local[2]")
        .appName("dse-iceberg-tests")
        .config("spark.jars", runtime)
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.dse", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.dse.type", "hadoop")
        .config("spark.sql.catalog.dse.warehouse", warehouse)
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield session
    session.stop()


def _documents_frame(spark, rows):
    from pyspark.sql.types import ArrayType, BooleanType, LongType, StringType, StructField, StructType

    schema = StructType(
        [
            StructField("doc_id", StringType(), False),
            StructField("title", StringType(), True),
            StructField("url", StringType(), True),
            StructField("text", StringType(), True),
            StructField("links", ArrayType(StringType()), True),
            StructField("version", LongType(), True),
            StructField("phase", StringType(), True),
            StructField("deleted", BooleanType(), False),
        ]
    )
    return spark.createDataFrame(rows, schema=schema)


def test_iceberg_delete_tombstone_prevents_stale_resurrection(iceberg_spark, tmp_path) -> None:
    from ingestion.iceberg_writer import IcebergWriter

    config = {
        "iceberg": {
            "catalog": "dse",
            "documents_table": "dse.documents",
            "rejections_table": "dse.ingestion_rejections",
            "runs_table": "dse.ingestion_runs",
            "warehouse": tmp_path.as_uri(),
        }
    }
    writer = IcebergWriter(iceberg_spark, config)
    writer.ensure_tables()
    writer.merge_documents(
        _documents_frame(
            iceberg_spark,
            [("1", "One", "https://example.test/1", "Body", [], 1, "0", False)],
        )
    )
    writer.merge_documents(
        _documents_frame(
            iceberg_spark,
            [("1", None, None, None, None, 2, "1", True)],
        )
    )
    writer.merge_documents(
        _documents_frame(
            iceberg_spark,
            [("1", "Stale", "https://example.test/1", "Old", [], 1, "0", False)],
        )
    )
    row = iceberg_spark.table(writer.documents_table).where("doc_id = '1'").first()
    assert row["deleted"] is True
    assert row["version"] == 2


def test_ingestion_pipeline_applies_phase_updates_with_tombstones(
    iceberg_spark,
    tmp_path,
) -> None:
    from ingestion.pipeline import run_ingestion

    config = {
        "iceberg": {
            "catalog": "dse",
            "documents_table": "dse.documents",
            "rejections_table": "dse.ingestion_rejections",
            "runs_table": "dse.ingestion_runs",
            "warehouse": tmp_path.as_uri(),
        },
        "paths": {
            "local": {"dataset_root": str(tmp_path)},
            "hdfs": {"datasets": (tmp_path / "datasets").as_uri()},
        },
    }
    phase0 = tmp_path / "pages.jsonl"
    phase0.write_text(
        '{"doc_id":"phase-a","url":"https://example.test/a","title":"A","text":"Alpha","links":[]}\n'
        '{"doc_id":"phase-b","url":"https://example.test/b","title":"B","text":"Beta","links":[]}\n',
        encoding="utf-8",
    )
    run_ingestion(
        phase=0,
        source=str(phase0),
        config=config,
        settings={},
        spark=iceberg_spark,
    )
    phase1 = tmp_path / "changes.jsonl"
    phase1.write_text(
        '{"doc_id":"phase-a","op":"DELETE","version":2}\n'
        '{"doc_id":"phase-b","op":"UPSERT","version":2,"url":"https://example.test/b",'
        '"title":"B2","text":"Beta updated","links":[]}\n',
        encoding="utf-8",
    )
    run_ingestion(
        phase=1,
        source=str(phase1),
        config=config,
        settings={},
        spark=iceberg_spark,
    )
    run_ingestion(
        phase=0,
        source=str(phase0),
        config=config,
        settings={},
        spark=iceberg_spark,
    )
    rows = {
        row["doc_id"]: row
        for row in iceberg_spark.table("dse.documents")
        .where("doc_id IN ('phase-a', 'phase-b')")
        .collect()
    }
    assert rows["phase-a"]["deleted"] is True
    assert rows["phase-a"]["version"] == 2
    assert rows["phase-b"]["deleted"] is False
    assert rows["phase-b"]["version"] == 2
    assert rows["phase-b"]["title"] == "B2"


def test_end_to_end_iceberg_to_searchable_export(
    iceberg_spark,
    tmp_path,
) -> None:
    from indexing.export import export_index
    from indexing.inverted_index import build_inverted_index
    from ingestion.pipeline import run_ingestion
    from pagerank.algorithm import calculate_pagerank
    from pagerank.graph_builder import build_graph
    from search_service.index_loader import load_index

    config = {
        "iceberg": {
            "catalog": "dse",
            "documents_table": "dse.e2e_documents",
            "rejections_table": "dse.e2e_ingestion_rejections",
            "runs_table": "dse.e2e_ingestion_runs",
            "warehouse": tmp_path.as_uri(),
        },
        "paths": {
            "local": {"dataset_root": str(tmp_path)},
            "hdfs": {"datasets": (tmp_path / "datasets").as_uri()},
        },
    }
    phase0 = tmp_path / "pages.jsonl"
    phase0.write_text(
        '{"doc_id":"e2e-a","url":"https://example.test/a","title":"Alpha",'
        '"text":"Distributed search systems","links":["https://example.test/b"]}\n'
        '{"doc_id":"e2e-b","url":"https://example.test/b","title":"Beta",'
        '"text":"Search engine ranking","links":[]}\n',
        encoding="utf-8",
    )
    run_ingestion(
        phase=0,
        source=str(phase0),
        config=config,
        settings={},
        spark=iceberg_spark,
    )
    documents = iceberg_spark.table("dse.e2e_documents").filter("deleted = false")
    index = build_inverted_index(documents)
    graph = build_graph(index.documents)
    rank = calculate_pagerank(graph.vertices, graph.edges, damping=0.85, iterations=15, tolerance=1e-6)
    export_root, metadata = export_index(
        spark=iceberg_spark,
        documents=index.documents,
        postings=index.postings,
        terms=index.terms,
        pagerank=rank.scores,
        output_root=tmp_path / "exports",
        version=0,
        phase=0,
    )
    snapshot = load_index(export_root)
    assert metadata["document_count"] == 2
    assert snapshot.document_count == 2
    assert set(snapshot.postings) == {"distributed", "search", "systems", "engine", "ranking"}
    assert abs(sum(snapshot.pagerank_scores.values()) - 1.0) < 1e-9


def test_iceberg_unknown_delete_creates_tombstone(iceberg_spark, tmp_path) -> None:
    from ingestion.iceberg_writer import IcebergWriter

    config = {
        "iceberg": {
            "catalog": "dse",
            "documents_table": "dse.documents",
            "rejections_table": "dse.ingestion_rejections",
            "runs_table": "dse.ingestion_runs",
            "warehouse": tmp_path.as_uri(),
        }
    }
    writer = IcebergWriter(iceberg_spark, config)
    writer.ensure_tables()
    writer.merge_documents(
        _documents_frame(
            iceberg_spark,
            [("missing", None, None, None, None, 2, "1", True)],
        )
    )
    row = iceberg_spark.table(writer.documents_table).where("doc_id = 'missing'").first()
    assert row is not None
    assert row["deleted"] is True
    assert row["version"] == 2
