"""Phase-aware ingestion record validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

PHASE_DEFAULT_VERSIONS = {0: 1, 1: 2}
MAX_VERSION = (1 << 63) - 1


@dataclass(frozen=True)
class ValidationResult:
    record: dict[str, Any] | None
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors and self.record is not None

    def __bool__(self) -> bool:
        return self.valid


def normalize_phase(phase: int | str) -> int:
    try:
        value = int(phase)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid phase: {phase}") from exc
    if value not in PHASE_DEFAULT_VERSIONS:
        raise ValueError(f"phase must be 0 or 1: {phase}")
    return value


def _valid_doc_id(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and "/" not in value
        and "?" not in value
        and "#" not in value
    )


def _valid_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.hostname)
    except ValueError:
        return False


def validate_payload(
    payload: Any,
    phase: int | str,
    default_version: int | None = None,
) -> ValidationResult:
    phase_number = normalize_phase(phase)
    fallback_version = default_version if default_version is not None else PHASE_DEFAULT_VERSIONS[phase_number]
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ValidationResult(None, ("record must be a JSON object",))

    op = payload.get("op", "UPSERT") if phase_number == 0 else payload.get("op")
    if phase_number == 0 and op != "UPSERT":
        errors.append("op must be UPSERT")
    if phase_number == 1 and op not in {"UPSERT", "DELETE"}:
        errors.append("op must be UPSERT or DELETE")

    doc_id = payload.get("doc_id")
    if not _valid_doc_id(doc_id):
        errors.append("doc_id must be a non-empty string without '/', '?' or '#'")
    elif not isinstance(doc_id, str) or doc_id != doc_id.strip():
        errors.append("doc_id must not contain surrounding whitespace")

    version = payload.get("version", fallback_version)
    if isinstance(version, bool) or not isinstance(version, int):
        errors.append("version must be an integer")
    elif version <= 0 or version > MAX_VERSION:
        errors.append(f"version must be between 1 and {MAX_VERSION}")

    normalized: dict[str, Any] = {
        "doc_id": doc_id.strip() if isinstance(doc_id, str) else None,
        "version": version if isinstance(version, int) and not isinstance(version, bool) else None,
        "phase": str(phase_number),
        "op": op if isinstance(op, str) else None,
    }

    if phase_number == 1 and op == "DELETE":
        return ValidationResult(normalized if not errors else None, tuple(errors))

    required = ("url", "title", "text", "links")
    for field in required:
        if field not in payload:
            errors.append(f"{field} is required")
    if "url" in payload and not _valid_url(payload.get("url")):
        errors.append("url must be an absolute http or https URL")
    for field in ("title", "text"):
        if field in payload and not isinstance(payload.get(field), str):
            errors.append(f"{field} must be a string")
    links = payload.get("links")
    if "links" in payload:
        if not isinstance(links, list):
            errors.append("links must be an array")
        elif not all(isinstance(link, str) and bool(link.strip()) for link in links):
            errors.append("links must contain only non-empty strings")

    if not errors:
        normalized.update(
            {
                "url": payload["url"],
                "title": payload["title"],
                "text": payload["text"],
                "links": list(payload["links"]),
            }
        )
    return ValidationResult(normalized if not errors else None, tuple(errors))


def validate_record(
    record: Any,
    phase: int | str,
    default_version: int | None = None,
) -> ValidationResult:
    return validate_payload(record, phase, default_version)


def validate_records(
    records: list[dict[str, Any]],
    phase: int | str,
    default_version: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        result = validate_payload(record, phase, default_version)
        if result.valid and result.record is not None:
            valid.append(result.record)
        else:
            rejections.append(
                {
                    "line_number": index,
                    "reason": "; ".join(result.errors),
                    "raw_line": json.dumps(record, ensure_ascii=False, sort_keys=True),
                    "phase": str(normalize_phase(phase)),
                }
            )
    return valid, rejections


def validate_dataframe(records: Any, phase: int | str, default_version: int | None = None) -> tuple[Any, Any]:
    from pyspark.sql.functions import col, concat_ws, udf
    from pyspark.sql.types import ArrayType, BooleanType, LongType, StringType, StructField, StructType

    phase_number = normalize_phase(phase)
    fallback_version = default_version if default_version is not None else PHASE_DEFAULT_VERSIONS[phase_number]

    def validate_row(raw_json: str, line_number: int, raw_line: str) -> tuple[Any, ...]:
        try:
            payload = json.loads(raw_json) if raw_json else {}
        except json.JSONDecodeError as exc:
            return (
                False,
                [f"malformed_json: {exc.msg}"],
                None,
                None,
                None,
                None,
                None,
                str(phase_number),
                None,
                int(line_number),
                raw_line,
            )
        result = validate_payload(payload, phase_number, fallback_version)
        record = result.record or {}
        return (
            result.valid,
            list(result.errors),
            record.get("doc_id"),
            record.get("url"),
            record.get("title"),
            record.get("text"),
            record.get("links"),
            record.get("version"),
            str(phase_number),
            record.get("op"),
            int(line_number),
            raw_line,
        )

    schema = StructType(
        [
            StructField("valid", BooleanType(), False),
            StructField("errors", ArrayType(StringType()), False),
            StructField("doc_id", StringType(), True),
            StructField("url", StringType(), True),
            StructField("title", StringType(), True),
            StructField("text", StringType(), True),
            StructField("links", ArrayType(StringType()), True),
            StructField("version", LongType(), True),
            StructField("phase", StringType(), False),
            StructField("op", StringType(), True),
            StructField("line_number", LongType(), False),
            StructField("raw_line", StringType(), True),
        ]
    )
    validator = udf(validate_row, schema)
    checked = records.withColumn(
        "validation",
        validator(col("raw_json"), col("line_number"), col("raw_line")),
    ).select("validation.*")
    valid = checked.filter(col("valid")).select(
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
    )
    rejected = checked.filter(~col("valid")).select(
        col("line_number"),
        concat_ws("; ", col("errors")).alias("reason"),
        col("raw_line"),
        col("phase"),
    )
    return valid, rejected


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate JSONL ingestion records")
    parser.add_argument("source", help="Local JSONL file")
    parser.add_argument("--phase", type=int, choices=(0, 1), required=True)
    parser.add_argument("--version", type=int, default=None)
    args = parser.parse_args()
    from ingestion.parser import parse_jsonl_file

    records, parse_rejections = parse_jsonl_file(args.source, args.phase)
    valid, validation_rejections = validate_records(records, args.phase, args.version)
    print(f"valid={len(valid)} rejected={len(parse_rejections) + len(validation_rejections)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
