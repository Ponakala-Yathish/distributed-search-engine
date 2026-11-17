from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    pa = None
    pq = None


REQUIRED_FILES = (
    "metadata.json",
    "documents.parquet",
    "postings.parquet",
    "terms.parquet",
    "pagerank.parquet",
)
REQUIRED_METADATA_FIELDS = (
    "version",
    "phase",
    "created_at",
    "document_count",
    "total_documents",
    "avg_document_length",
    "bm25",
    "pagerank",
    "files",
)


class IndexValidationError(ValueError):
    pass


@dataclass(frozen=True)
class DocumentRecord:
    doc_id: str
    title: str
    url: str
    text: str
    doc_length: int


@dataclass(frozen=True)
class TermStats:
    term: str
    df: int
    idf: float


@dataclass(frozen=True)
class IndexSnapshot:
    version: str
    phase: str
    created_at: str
    document_count: int
    total_documents: int
    avg_document_length: float
    bm25: dict[str, float]
    pagerank: dict[str, float | int]
    documents: dict[str, DocumentRecord]
    postings: dict[str, dict[str, int]]
    terms: dict[str, TermStats]
    pagerank_scores: dict[str, float]
    version_path: Path

    @property
    def doc_lengths(self) -> dict[str, int]:
        return {doc_id: document.doc_length for doc_id, document in self.documents.items()}

    @property
    def term_count(self) -> int:
        return len(self.terms)

    @property
    def posting_count(self) -> int:
        return sum(len(postings) for postings in self.postings.values())


def _require_pyarrow() -> None:
    if pa is None or pq is None:
        raise ImportError("pyarrow is required to load search indexes")


def _read_metadata(version_path: Path) -> dict[str, Any]:
    metadata_path = version_path / "metadata.json"
    if not metadata_path.is_file():
        raise IndexValidationError(f"missing metadata file: {metadata_path}")
    if metadata_path.stat().st_size == 0:
        raise IndexValidationError(f"metadata file is empty: {metadata_path}")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndexValidationError(f"invalid metadata file: {exc}") from exc
    if not isinstance(metadata, dict):
        raise IndexValidationError("metadata must be a JSON object")
    missing = [field for field in REQUIRED_METADATA_FIELDS if field not in metadata]
    if missing:
        raise IndexValidationError(f"metadata is missing fields: {', '.join(missing)}")
    return metadata


def _validate_file_list(metadata: dict[str, Any]) -> None:
    files = metadata["files"]
    names: set[str] = set()
    if isinstance(files, dict):
        for key, value in files.items():
            names.add(str(key))
            if isinstance(value, str):
                names.add(Path(value).name)
    elif isinstance(files, list):
        for value in files:
            if isinstance(value, str):
                names.add(Path(value).name)
            elif isinstance(value, dict):
                candidate = value.get("name", value.get("filename", value.get("path")))
                if candidate is not None:
                    names.add(Path(str(candidate)).name)
    else:
        raise IndexValidationError("metadata files must be a list or object")
    missing = [name for name in REQUIRED_FILES if name != "metadata.json" and name not in names]
    if missing:
        raise IndexValidationError(f"metadata does not list required files: {', '.join(missing)}")


def _data_path(version_path: Path, filename: str) -> Path:
    path = version_path / filename
    if path.is_file():
        if path.stat().st_size == 0:
            raise IndexValidationError(f"index file is empty: {path}")
        return path
    if path.is_dir():
        parquet_files = [item for item in path.rglob("*.parquet") if item.is_file() and item.stat().st_size > 0]
        if parquet_files:
            return path
        raise IndexValidationError(f"index directory has no nonempty parquet files: {path}")
    raise IndexValidationError(f"missing index file: {path}")


def _read_parquet(version_path: Path, filename: str, required_columns: tuple[str, ...]) -> list[dict[str, Any]]:
    _require_pyarrow()
    path = _data_path(version_path, filename)
    try:
        table = pq.read_table(path)
    except Exception as exc:
        raise IndexValidationError(f"unable to read {filename}: {exc}") from exc
    names = set(table.schema.names)
    missing = [column for column in required_columns if column not in names]
    if missing:
        raise IndexValidationError(f"{filename} is missing columns: {', '.join(missing)}")
    return cast(list[dict[str, Any]], table.to_pylist())


def _validate_column_types(schema: Any, filename: str, expected: dict[str, tuple[str, ...]]) -> None:
    for column, type_names in expected.items():
        try:
            field = schema.field(column)
        except KeyError as exc:
            raise IndexValidationError(f"{filename} is missing column: {column}") from exc
        if str(field.type) not in type_names:
            expected_names = ", ".join(type_names)
            raise IndexValidationError(f"{filename}.{column} must have type {expected_names}")


def _parquet_schema(path: Path) -> Any:
    if path.is_dir():
        return pq.ParquetDataset(path).schema
    return pq.read_schema(path)


def _doc_id(value: Any, field: str) -> str:
    if isinstance(value, bool) or value is None:
        raise IndexValidationError(f"{field} must be a non-empty string or integer")
    if isinstance(value, int):
        result = str(value)
    elif isinstance(value, str):
        result = value
    else:
        raise IndexValidationError(f"{field} must be a non-empty string or integer")
    if not result:
        raise IndexValidationError(f"{field} must not be empty")
    return result


def _string(value: Any, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise IndexValidationError(f"{field} must be a string")
    return value


def _integer(value: Any, field: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IndexValidationError(f"{field} must be an integer")
    if minimum is not None and value < minimum:
        raise IndexValidationError(f"{field} must be at least {minimum}")
    return int(value)


def _number(value: Any, field: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise IndexValidationError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise IndexValidationError(f"{field} must be finite")
    if minimum is not None and result < minimum:
        raise IndexValidationError(f"{field} must be at least {minimum}")
    return result


def _load_documents(version_path: Path) -> dict[str, DocumentRecord]:
    _require_pyarrow()
    path = _data_path(version_path, "documents.parquet")
    try:
        schema = _parquet_schema(path)
    except Exception as exc:
        raise IndexValidationError(f"unable to inspect documents.parquet: {exc}") from exc
    _validate_column_types(
        schema,
        "documents.parquet",
        {
            "doc_id": ("string", "int64", "int32"),
            "title": ("string",),
            "url": ("string",),
            "text": ("string",),
            "document_length": ("int64", "int32"),
        },
    )
    rows = _read_parquet(version_path, "documents.parquet", ("doc_id", "title", "url", "text", "document_length"))
    documents: dict[str, DocumentRecord] = {}
    for row in rows:
        doc_id = _doc_id(row["doc_id"], "documents.doc_id")
        if doc_id in documents:
            raise IndexValidationError(f"duplicate document id: {doc_id}")
        documents[doc_id] = DocumentRecord(
            doc_id=doc_id,
            title=_string(row["title"], "documents.title"),
            url=_string(row["url"], "documents.url"),
            text=_string(row["text"], "documents.text"),
            doc_length=_integer(row["document_length"], "documents.document_length", 0),
        )
    if not documents:
        raise IndexValidationError("documents.parquet contains no documents")
    return documents


def _load_postings(
    version_path: Path,
    document_ids: set[str],
) -> dict[str, dict[str, int]]:
    _require_pyarrow()
    path = _data_path(version_path, "postings.parquet")
    try:
        schema = _parquet_schema(path)
    except Exception as exc:
        raise IndexValidationError(f"unable to inspect postings.parquet: {exc}") from exc
    _validate_column_types(
        schema,
        "postings.parquet",
        {
            "term": ("string",),
            "doc_id": ("string", "int64", "int32"),
            "tf": ("int64", "int32"),
        },
    )
    rows = _read_parquet(version_path, "postings.parquet", ("term", "doc_id", "tf"))
    postings: dict[str, dict[str, int]] = {}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        term = _string(row["term"], "postings.term")
        if not term:
            raise IndexValidationError("postings.term must not be empty")
        doc_id = _doc_id(row["doc_id"], "postings.doc_id")
        if doc_id not in document_ids:
            raise IndexValidationError(f"postings references unknown document: {doc_id}")
        key = (term, doc_id)
        if key in seen:
            raise IndexValidationError(f"duplicate posting for term {term!r} and document {doc_id}")
        seen.add(key)
        postings.setdefault(term, {})[doc_id] = _integer(row["tf"], "postings.tf", 1)
    return postings


def _load_terms(version_path: Path, postings: dict[str, dict[str, int]]) -> dict[str, TermStats]:
    _require_pyarrow()
    path = _data_path(version_path, "terms.parquet")
    try:
        schema = _parquet_schema(path)
    except Exception as exc:
        raise IndexValidationError(f"unable to inspect terms.parquet: {exc}") from exc
    _validate_column_types(
        schema,
        "terms.parquet",
        {
            "term": ("string",),
            "df": ("int64", "int32"),
            "idf": ("double", "float64", "float32"),
        },
    )
    rows = _read_parquet(version_path, "terms.parquet", ("term", "df", "idf"))
    terms: dict[str, TermStats] = {}
    for row in rows:
        term = _string(row["term"], "terms.term")
        if not term:
            raise IndexValidationError("terms.term must not be empty")
        if term in terms:
            raise IndexValidationError(f"duplicate term: {term}")
        document_frequency = _integer(row["df"], "terms.df", 0)
        posting_frequency = len(postings.get(term, {}))
        if document_frequency != posting_frequency:
            raise IndexValidationError(
                f"term {term!r} has df {document_frequency} but {posting_frequency} postings"
            )
        terms[term] = TermStats(
            term=term,
            df=document_frequency,
            idf=_number(row["idf"], "terms.idf"),
        )
    posting_only = sorted(set(postings) - set(terms))
    if posting_only:
        raise IndexValidationError(f"postings contain terms missing from terms.parquet: {posting_only[0]}")
    if not terms:
        raise IndexValidationError("terms.parquet contains no terms")
    return terms


def _load_pagerank(version_path: Path, document_ids: set[str]) -> dict[str, float]:
    _require_pyarrow()
    path = _data_path(version_path, "pagerank.parquet")
    try:
        schema = _parquet_schema(path)
    except Exception as exc:
        raise IndexValidationError(f"unable to inspect pagerank.parquet: {exc}") from exc
    _validate_column_types(
        schema,
        "pagerank.parquet",
        {
            "doc_id": ("string", "int64", "int32"),
            "pagerank": ("double", "float64", "float32"),
        },
    )
    rows = _read_parquet(version_path, "pagerank.parquet", ("doc_id", "pagerank"))
    scores: dict[str, float] = {}
    for row in rows:
        doc_id = _doc_id(row["doc_id"], "pagerank.doc_id")
        if doc_id in scores:
            raise IndexValidationError(f"duplicate pagerank entry for document: {doc_id}")
        scores[doc_id] = _number(row["pagerank"], "pagerank.pagerank", 0.0)
    missing = document_ids - set(scores)
    if missing:
        raise IndexValidationError(f"pagerank is missing document: {sorted(missing)[0]}")
    extra = set(scores) - document_ids
    if extra:
        raise IndexValidationError(f"pagerank contains unknown document: {sorted(extra)[0]}")
    return scores


def _validate_metadata_values(metadata: dict[str, Any], document_count: int, avg_document_length: float) -> None:
    version = metadata["version"]
    if isinstance(version, bool) or not isinstance(version, str | int) or not str(version).strip():
        raise IndexValidationError("metadata.version must be a non-empty string or integer")
    if not isinstance(metadata["phase"], str) or not metadata["phase"].strip():
        raise IndexValidationError("metadata.phase must be a non-empty string")
    if not isinstance(metadata["created_at"], str) or not metadata["created_at"].strip():
        raise IndexValidationError("metadata.created_at must be a non-empty string")
    try:
        datetime.fromisoformat(metadata["created_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise IndexValidationError("metadata.created_at must be an ISO-8601 timestamp") from exc
    declared_count = _integer(metadata["document_count"], "metadata.document_count", 1)
    if declared_count != document_count:
        raise IndexValidationError(
            f"metadata.document_count is {declared_count} but documents.parquet contains {document_count} documents"
        )
    total_documents = _integer(metadata["total_documents"], "metadata.total_documents", 1)
    if total_documents != document_count:
        raise IndexValidationError(
            f"metadata.total_documents is {total_documents} but documents.parquet contains {document_count} documents"
        )
    declared_average = _number(metadata["avg_document_length"], "metadata.avg_document_length", 0.0)
    tolerance = max(1e-6, abs(avg_document_length) * 1e-6)
    if not math.isclose(declared_average, avg_document_length, rel_tol=1e-6, abs_tol=tolerance):
        raise IndexValidationError(
            f"metadata.avg_document_length is {declared_average} but computed value is {avg_document_length}"
        )
    bm25 = metadata["bm25"]
    pagerank = metadata["pagerank"]
    if not isinstance(bm25, dict) or not isinstance(pagerank, dict):
        raise IndexValidationError("metadata bm25 and pagerank values must be objects")
    k1 = _number(bm25.get("k1"), "metadata.bm25.k1", 0.0)
    b = _number(bm25.get("b"), "metadata.bm25.b", 0.0)
    if k1 < 0:
        raise IndexValidationError("metadata.bm25.k1 must not be negative")
    if not 0 <= b <= 1:
        raise IndexValidationError("metadata.bm25.b must be between zero and one")
    _number(pagerank.get("damping"), "metadata.pagerank.damping", 0.0)
    _integer(pagerank.get("iterations"), "metadata.pagerank.iterations", 0)
    _number(pagerank.get("tolerance"), "metadata.pagerank.tolerance", 0.0)


def load_index(version_path: str | Path) -> IndexSnapshot:
    path = Path(version_path).expanduser().resolve()
    if not path.is_dir():
        raise IndexValidationError(f"version directory does not exist: {path}")
    for filename in REQUIRED_FILES:
        _data_path(path, filename)
    metadata = _read_metadata(path)
    _validate_file_list(metadata)
    documents = _load_documents(path)
    document_ids = set(documents)
    postings = _load_postings(path, document_ids)
    terms = _load_terms(path, postings)
    pagerank_scores = _load_pagerank(path, document_ids)
    avg_document_length = sum(document.doc_length for document in documents.values()) / len(documents)
    _validate_metadata_values(metadata, len(documents), avg_document_length)
    total_documents = int(metadata["total_documents"])
    for term, stats in terms.items():
        expected_idf = math.log(
            1.0 + (total_documents - stats.df + 0.5) / (stats.df + 0.5)
        )
        if not math.isclose(stats.idf, expected_idf, rel_tol=1e-9, abs_tol=1e-12):
            raise IndexValidationError(
                f"term {term!r} has idf {stats.idf} but expected {expected_idf}"
            )
    return IndexSnapshot(
        version=str(metadata["version"]),
        phase=str(metadata["phase"]),
        created_at=str(metadata["created_at"]),
        document_count=len(documents),
        total_documents=int(metadata["total_documents"]),
        avg_document_length=avg_document_length,
        bm25={"k1": float(metadata["bm25"]["k1"]), "b": float(metadata["bm25"]["b"])},
        pagerank=dict(metadata["pagerank"]),
        documents=documents,
        postings=postings,
        terms=terms,
        pagerank_scores=pagerank_scores,
        version_path=path,
    )


class IndexLoader:
    def __init__(self, serving_root: str | Path | None = None) -> None:
        self.serving_root = Path(serving_root).expanduser().resolve() if serving_root else None

    def load(self, version_path: str | Path) -> IndexSnapshot:
        return load_index(version_path)

    def load_version(self, version: str) -> IndexSnapshot:
        if self.serving_root is None:
            raise ValueError("serving_root is required to load a version by name")
        return load_index(self.serving_root / version)
