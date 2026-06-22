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


def test_writer_rejects_increasing_score(tmp_path: Path):
    rows = [_row(i + 1, float(i)) for i in range(100)]  # 0..99, ascending
    with pytest.raises(SubmissionError):
        write_submission(rows, tmp_path / "x.csv")


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
