from __future__ import annotations

import pytest


def _pyspark_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("pyspark") is not None


@pytest.fixture(scope="module")
def spark_session():
    if not _pyspark_available():
        pytest.skip("PySpark is not installed")

    import os
    import sys

    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

    from pyspark.sql import SparkSession

    session = (
        SparkSession.builder.master("local[2]")
        .appName("dse-tests")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield session
    session.stop()


def test_distributed_postings_are_built_with_spark(spark_session) -> None:
    from indexing.inverted_index import build_inverted_index

    documents = spark_session.createDataFrame(
        [
            ("1", "April month April"),
            ("2", "August month"),
        ],
        ["doc_id", "text"],
    )
    from pyspark.sql.functions import sum as spark_sum

    index = build_inverted_index(documents)
    postings = {
        row["term"]: row["total_tf"]
        for row in index.postings.groupBy("term").agg(spark_sum("tf").alias("total_tf")).collect()
    }
    assert postings["april"] == 2
    assert postings["month"] == 2
    assert index.terms.filter("term = 'april'").first()["df"] == 1


def test_spark_parser_preserves_source_line_numbers(spark_session, tmp_path) -> None:
    from ingestion.parser import parse_jsonl_spark

    source = tmp_path / "pages.jsonl"
    source.write_text(
        '{"doc_id":"1","url":"https://example.test/1","title":"One","text":"Body","links":[]}\n'
        "not-json\n",
        encoding="utf-8",
    )
    records, rejections = parse_jsonl_spark(spark_session, str(source))
    assert records.count() == 1
    rejection = rejections.collect()[0]
    assert rejection["line_number"] == 2
    assert rejection["raw_line"] == "not-json"


def test_spark_validation_rejects_unknown_phase_zero_operation(spark_session) -> None:
    from ingestion.validation import validate_dataframe

    records = spark_session.createDataFrame(
        [
            (
                "1",
                "https://example.test/1",
                "One",
                "Body",
                ["https://example.test/2"],
                1,
                "0",
                "UNKNOWN",
                1,
                "raw",
                '{"doc_id":"1","url":"https://example.test/1","title":"One","text":"Body","links":[],"op":"UNKNOWN"}',
            ),
        ],
        [
            "doc_id",
            "url",
            "title",
            "text",
            "links",
            "version",
            "phase",
            "op",
            "line_number",
            "raw_line",
            "raw_json",
        ],
    )
    valid, rejected = validate_dataframe(records, 0, 1)
    assert valid.count() == 0
    assert "op must be UPSERT" in rejected.collect()[0]["reason"]


def test_spark_deduplication_uses_links_as_deterministic_tiebreaker(spark_session) -> None:
    from ingestion.deduplication import deduplicate_dataframe

    records = spark_session.createDataFrame(
        [
            ("1", "https://example.test/1", "One", "Body", ["z"], 1, "0", "UPSERT"),
            ("1", "https://example.test/1", "One", "Body", ["a"], 1, "0", "UPSERT"),
        ],
        ["doc_id", "url", "title", "text", "links", "version", "phase", "op"],
    )
    selected = deduplicate_dataframe(records).collect()
    assert len(selected) == 1
    assert selected[0]["links"] == ["a"]


def test_pagerank_conserves_mass_and_handles_dangling_nodes(spark_session) -> None:
    from pagerank.algorithm import calculate_pagerank

    vertices = spark_session.createDataFrame([("1",), ("2",), ("3",)], ["doc_id"])
    edges = spark_session.createDataFrame([("1", "2")], ["src", "dst"])
    result = calculate_pagerank(vertices, edges, damping=0.85, iterations=15, tolerance=1e-6)
    scores = {row["doc_id"]: row["score"] for row in result.scores.collect()}
    assert abs(sum(scores.values()) - 1.0) < 1e-9
    assert scores["2"] > scores["3"]


def test_graph_resolves_duplicate_urls_to_one_destination(spark_session) -> None:
    from pagerank.graph_builder import build_graph

    documents = spark_session.createDataFrame(
        [
            ("1", "https://example.test/1", ["https://example.test/shared"]),
            ("2", "https://example.test/shared", []),
            ("3", "https://example.test/shared", []),
        ],
        ["doc_id", "url", "links"],
    )
    edges = {(row["src"], row["dst"]) for row in build_graph(documents).edges.collect()}
    assert edges == {("1", "2")}


def test_exporter_round_trip_validates_spark_index(spark_session, tmp_path) -> None:
    from indexing.export import export_index, validate_export
    from indexing.inverted_index import build_inverted_index

    documents = spark_session.createDataFrame(
        [
            ("1", "https://example.test/1", "One", "April month April", ["https://example.test/2"], 1),
            ("2", "https://example.test/2", "Two", "August month", ["https://example.test/1"], 1),
        ],
        ["doc_id", "url", "title", "text", "links", "version"],
    )
    index = build_inverted_index(documents)
    pagerank = spark_session.createDataFrame(
        [("1", 0.6), ("2", 0.4)],
        ["doc_id", "score"],
    )
    path, metadata = export_index(
        spark=spark_session,
        documents=index.documents,
        postings=index.postings,
        terms=index.terms,
        pagerank=pagerank,
        output_root=tmp_path,
        version=0,
        phase=0,
    )
    validated = validate_export(spark_session, path)
    assert validated["document_count"] == 2
    assert metadata["total_documents"] == 2
    idf = index.terms.filter("term = 'april'").first()["idf"]
    assert abs(idf - 0.6931471805599453) < 1e-12

    from search_service.index_loader import load_index

    snapshot = load_index(path)
    assert snapshot.document_count == 2
    assert snapshot.terms["april"].idf == idf


def test_graph_maps_url_links_to_document_ids(spark_session) -> None:
    from pagerank.graph_builder import build_graph

    documents = spark_session.createDataFrame(
        [
            ("1", "https://example.test/1", ["https://example.test/2"]),
            ("2", "https://example.test/2", []),
        ],
        ["doc_id", "url", "links"],
    )
    graph = build_graph(documents)
    edges = {(row["src"], row["dst"]) for row in graph.edges.collect()}
    assert edges == {("1", "2")}
