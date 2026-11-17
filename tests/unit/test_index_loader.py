from __future__ import annotations

import json
from pathlib import Path

import pytest

from search_service.index_loader import IndexValidationError, load_index


def test_loader_validates_and_loads_export(index_directory: Path) -> None:
    snapshot = load_index(index_directory)
    assert snapshot.version == "0"
    assert snapshot.document_count == 2
    assert snapshot.term_count == 3
    assert snapshot.pagerank_scores["1"] == 0.6


def test_loader_rejects_missing_pagerank(index_directory: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    pq.write_table(
        pa.table({"doc_id": ["1"], "pagerank": [0.6]}),
        index_directory / "pagerank.parquet",
    )
    with pytest.raises(IndexValidationError, match="missing document"):
        load_index(index_directory)


def test_loader_rejects_inconsistent_metadata(index_directory: Path) -> None:
    metadata_path = index_directory / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["document_count"] = 3
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(IndexValidationError, match="document_count"):
        load_index(index_directory)


def test_loader_rejects_empty_file(index_directory: Path) -> None:
    (index_directory / "terms.parquet").write_bytes(b"")
    with pytest.raises(IndexValidationError, match="empty"):
        load_index(index_directory)
