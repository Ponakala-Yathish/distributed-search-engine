"""Raw JSONL parsing with line-aware rejection reporting."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ParseResult:
    record: dict[str, Any] | None
    rejection: dict[str, Any] | None

    @property
    def valid(self) -> bool:
        return self.record is not None


def parse_jsonl_line(raw_line: str, line_number: int, phase: int = 0) -> ParseResult:
    try:
        value = json.loads(raw_line)
    except json.JSONDecodeError as exc:
        return ParseResult(
            None,
            {
                "line_number": int(line_number),
                "reason": f"malformed_json: {exc.msg}",
                "raw_line": raw_line,
                "phase": str(phase),
            },
        )
    if not isinstance(value, dict):
        return ParseResult(
            None,
            {
                "line_number": int(line_number),
                "reason": "malformed_record: expected a JSON object",
                "raw_line": raw_line,
                "phase": str(phase),
            },
        )
    return ParseResult(value, None)


def parse_jsonl(raw: str, phase: int = 0) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(raw.splitlines(), start=1):
        result = parse_jsonl_line(raw_line, line_number, phase)
        if result.record is not None:
            records.append(result.record)
        if result.rejection is not None:
            rejections.append(result.rejection)
    return records, rejections


def parse_jsonl_file(path: str | Path, phase: int = 0) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with Path(path).open(encoding="utf-8") as stream:
        return parse_jsonl(stream.read(), phase)


def parse_jsonl_spark(spark: Any, path: str, phase: int = 0) -> tuple[Any, Any]:
    from pyspark.sql.types import ArrayType, LongType, StringType, StructField, StructType

    def parse_partition(entries: Any) -> Any:
        for raw_line, line_number in entries:
            result = parse_jsonl_line(raw_line, line_number, phase)
            if result.record is None:
                rejection = result.rejection or {}
                yield (
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    str(phase),
                    None,
                    int(line_number),
                    raw_line,
                    None,
                    rejection.get("reason", "malformed_record"),
                )
                continue
            record = result.record
            links = record.get("links")
            safe_links = links if isinstance(links, list) and all(isinstance(item, str) for item in links) else None
            version = record.get("version")
            safe_version = version if isinstance(version, int) and not isinstance(version, bool) else None
            canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            yield (
                record.get("doc_id") if isinstance(record.get("doc_id"), str) else None,
                record.get("url") if isinstance(record.get("url"), str) else None,
                record.get("title") if isinstance(record.get("title"), str) else None,
                record.get("text") if isinstance(record.get("text"), str) else None,
                safe_links,
                safe_version,
                str(phase),
                record.get("op") if isinstance(record.get("op"), str) else None,
                int(line_number),
                raw_line,
                canonical,
                None,
            )

    schema = StructType(
        [
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
            StructField("raw_json", StringType(), True),
            StructField("reason", StringType(), True),
        ]
    )
    parsed = spark.createDataFrame(
        spark.sparkContext.textFile(path).zipWithIndex().map(
            lambda entry: (entry[0], entry[1] + 1)
        ).mapPartitions(parse_partition),
        schema=schema,
    )
    records = parsed.filter("reason IS NULL").select(
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
    )
    rejections = parsed.filter("reason IS NOT NULL").select(
        "line_number",
        "reason",
        "raw_line",
        "phase",
    )
    return records, rejections


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Parse and validate a raw JSONL ingestion file")
    parser.add_argument("source", help="Local JSONL file")
    parser.add_argument("--phase", type=int, choices=(0, 1), default=0)
    args = parser.parse_args()
    records, rejections = parse_jsonl_file(args.source, args.phase)
    print(f"records={len(records)} rejections={len(rejections)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
