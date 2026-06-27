"""Unit tests for the lightweight JSON-Schema validator + diff helper."""

from __future__ import annotations

from talentry.io.candidates import iter_candidate_records
from talentry.io.schema import (
    diff_against_schema,
    load_schema,
    validate_batch,
    validate_candidate,
)
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "raw" / "sample_candidates.json"


def test_schema_loads_and_has_expected_top_level_keys() -> None:
    schema = load_schema()
    assert schema["title"].lower().startswith("redrob")
    assert "candidate_id" in schema["required"]
    assert "redrob_signals" in schema["required"]


def test_valid_records_pass_validation() -> None:
    recs = list(iter_candidate_records(SAMPLE))[:5]
    assert recs, "fixture missing"
    for r in recs:
        errors = validate_candidate(r)
        assert errors == [], f"sample fixture must be schema-valid: {errors[:2]}"


def test_missing_required_field_is_caught() -> None:
    bad = {"candidate_id": "CAND_0000001"}
    errors = validate_candidate(bad)
    codes = {e.code for e in errors}
    assert "missing_required" in codes
    paths = {e.path for e in errors}
    assert any(p.startswith("profile") or p == "profile" for p in paths)


def test_pattern_mismatch_on_candidate_id() -> None:
    bad = {"candidate_id": "WRONG_ID"}
    errors = validate_candidate(bad)
    assert any(e.code == "pattern_mismatch" for e in errors)


def test_enum_violation_on_company_size() -> None:
    recs = list(iter_candidate_records(SAMPLE))[:1]
    rec = recs[0]
    rec = {**rec, "profile": {**rec["profile"], "current_company_size": "weird"}}
    errors = validate_candidate(rec)
    assert any(e.code == "enum_violation" for e in errors)


def test_batch_report_counts_invalid_rows() -> None:
    good = list(iter_candidate_records(SAMPLE))[:3]
    bad = {"candidate_id": "BAD"}
    report = validate_batch(good + [bad])
    assert report.n_total == 4
    assert report.n_valid == 3
    assert report.n_invalid == 1
    assert report.first_invalid_index == 3


def test_diff_payload_has_red_lines_for_missing_required() -> None:
    diff = diff_against_schema({"candidate_id": "CAND_0000001"})
    kinds = {line["kind"] for line in diff["lines"]}
    assert "missing" in kinds
