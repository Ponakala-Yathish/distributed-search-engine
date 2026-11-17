from __future__ import annotations

from ingestion.deduplication import deduplicate_records
from ingestion.parser import parse_jsonl, parse_jsonl_line
from ingestion.validation import validate_payload, validate_records


def test_parser_rejects_malformed_json_without_losing_line_number() -> None:
    result = parse_jsonl_line('{"doc_id":', 17, 0)
    assert not result.valid
    assert result.rejection is not None
    assert result.rejection["line_number"] == 17
    assert "malformed_json" in result.rejection["reason"]


def test_parser_collects_valid_and_invalid_records() -> None:
    records, rejections = parse_jsonl('{"doc_id":"1"}\nnot-json\n')
    assert records == [{"doc_id": "1"}]
    assert len(rejections) == 1


def test_validation_requires_documented_upsert_fields() -> None:
    result = validate_payload({"doc_id": "1"}, 0)
    assert not result.valid
    assert "url is required" in result.errors
    assert "title is required" in result.errors
    assert "text is required" in result.errors
    assert "links is required" in result.errors


def test_phase_delete_accepts_only_identifier_and_operation() -> None:
    result = validate_payload({"doc_id": "1", "op": "DELETE"}, 1)
    assert result.valid
    assert result.record is not None
    assert result.record["version"] == 2


def test_invalid_version_is_rejected() -> None:
    payload = {
        "doc_id": "1",
        "url": "https://example.test/1",
        "title": "One",
        "text": "Text",
        "links": [],
        "version": 0,
    }
    result = validate_payload(payload, 0)
    assert not result.valid
    assert any(error.startswith("version must be between 1 and") for error in result.errors)


def test_highest_version_wins_deterministically() -> None:
    base = {
        "doc_id": "1",
        "url": "https://example.test/1",
        "title": "One",
        "text": "Text",
        "links": [],
        "phase": "0",
        "op": "UPSERT",
    }
    records = [
        {**base, "version": 1, "title": "Old"},
        {**base, "version": 3, "title": "New"},
        {**base, "version": 2, "title": "Middle"},
    ]
    result = deduplicate_records(records)
    assert len(result) == 1
    assert result[0]["title"] == "New"


def test_validation_rejections_are_not_silently_dropped() -> None:
    valid, rejected = validate_records([{"doc_id": "1"}], 0)
    assert valid == []
    assert len(rejected) == 1
    assert rejected[0]["reason"]
