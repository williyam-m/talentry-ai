import re
from pathlib import Path

import pytest

from talentry.core.models import RankedCandidate, ScoreBreakdown
from talentry.io.submission import SubmissionError, write_submission


def _row(idx: int, score: float) -> RankedCandidate:
    return RankedCandidate(
        candidate_id=f"CAND_{idx:07d}",
        rank=idx,
        score=score,
        reasoning="ok",
        breakdown=ScoreBreakdown(),
    )


def test_writer_rejects_wrong_row_count(tmp_path: Path):
    with pytest.raises(SubmissionError):
        write_submission([_row(1, 1.0)], tmp_path / "x.csv")


def test_writer_canonicalises_order(tmp_path: Path):
    """Strict mode re-sorts by (score DESC, candidate_id ASC) and re-issues
    ranks so the output is always validator-clean even when the caller hands
    in a list whose ranks/scores disagree (e.g. after CSV quantisation
    collapsed ties)."""
    # Input: scores 0..99 ascending, ranks 1..100 - obviously inconsistent.
    rows = [_row(i + 1, float(i)) for i in range(100)]
    out = write_submission(rows, tmp_path / "x.csv")
    lines = out.read_text().strip().splitlines()
    # First data row must be the highest-scoring candidate (CAND_0000100 @ 99.0)
    first = lines[1].split(",")
    assert first[0] == "CAND_0000100"
    assert first[1] == "1"
    # Last data row is the lowest-scoring (CAND_0000001 @ 0.0)
    last = lines[-1].split(",")
    assert last[0] == "CAND_0000001"
    assert last[1] == "100"



def test_writer_produces_valid_csv(tmp_path: Path):
    rows = [_row(i + 1, 1.0 - i * 0.001) for i in range(100)]
    out = write_submission(rows, tmp_path / "submission.csv")
    text = out.read_text()
    assert text.startswith("candidate_id,rank,score,reasoning\n")
    # 101 lines = header + 100 data rows
    assert len(text.strip().splitlines()) == 101
    # All candidate ids match the schema regex
    for line in text.strip().splitlines()[1:]:
        cid = line.split(",", 1)[0]
        assert re.match(r"^CAND_[0-9]{7}$", cid)


def test_nonstrict_mode_writes_anything(tmp_path: Path):
    out = write_submission([_row(1, 0.9), _row(2, 0.8)], tmp_path / "x.csv", strict=False)
    assert "CAND_0000001" in out.read_text()
