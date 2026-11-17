from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def index_directory(tmp_path: Path) -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq

    root = tmp_path / "index-v0"
    root.mkdir()
    pq.write_table(
        pa.table(
            {
                "doc_id": ["1", "2"],
                "title": ["April", "August"],
                "url": ["https://example.test/april", "https://example.test/august"],
                "text": ["April is a month", "August is a month"],
                "document_length": [4, 4],
            }
        ),
        root / "documents.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "term": ["april", "august", "month"],
                "doc_id": ["1", "2", "1"],
                "tf": [1, 1, 1],
            }
        ),
        root / "postings.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "term": ["april", "august", "month"],
                "df": [1, 1, 1],
                "idf": [0.6931471805599453, 0.6931471805599453, 0.6931471805599453],
            }
        ),
        root / "terms.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "doc_id": ["1", "2"],
                "pagerank": [0.6, 0.4],
            }
        ),
        root / "pagerank.parquet",
    )
    metadata = {
        "version": 0,
        "phase": "0",
        "created_at": "2026-01-01T00:00:00+00:00",
        "document_count": 2,
        "total_documents": 2,
        "avg_document_length": 4.0,
        "bm25": {"k1": 1.2, "b": 0.75},
        "pagerank": {"damping": 0.85, "iterations": 15, "tolerance": 0.000001},
        "files": {
            "documents.parquet": "documents.parquet",
            "postings.parquet": "postings.parquet",
            "terms.parquet": "terms.parquet",
            "pagerank.parquet": "pagerank.parquet",
        },
    }
    (root / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return root
