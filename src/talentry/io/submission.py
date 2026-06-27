"""Submission CSV writer - strictly conforming to `validate_submission.py`.

The official validator (`validate_submission.py`) enforces:

1. Exactly the header ``candidate_id,rank,score,reasoning``.
2. Exactly 100 data rows.
3. Each ``rank`` 1..100 used once.
4. ``candidate_id`` matches ``^CAND_[0-9]{7}$``.
5. ``score`` non-increasing as rank increases.
6. Equal-score tie-break: ``candidate_id`` ascending.

We re-implement those invariants here so the writer **cannot** produce a CSV
the validator would reject - failing loudly at write time is much friendlier
than discovering the problem at upload time.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from pathlib import Path

from talentry.core.models import RankedCandidate

HEADER: tuple[str, ...] = ("candidate_id", "rank", "score", "reasoning")
_CAND_RE = re.compile(r"^CAND_[0-9]{7}$")


class SubmissionError(ValueError):
    """Raised when the writer is asked to emit an invalid submission."""


def _enforce_invariants(rows: list[RankedCandidate]) -> list[RankedCandidate]:
    if len(rows) != 100:
        raise SubmissionError(f"expected exactly 100 rows, got {len(rows)}")

    seen_ranks: set[int] = set()
    seen_ids: set[str] = set()
    for r in rows:
        if not _CAND_RE.match(r.candidate_id):
            raise SubmissionError(f"candidate_id '{r.candidate_id}' violates CAND_XXXXXXX format")
        if r.candidate_id in seen_ids:
            raise SubmissionError(f"duplicate candidate_id: {r.candidate_id}")
        seen_ids.add(r.candidate_id)
        if not 1 <= r.rank <= 100:
            raise SubmissionError(f"rank {r.rank} out of [1,100] for {r.candidate_id}")
        if r.rank in seen_ranks:
            raise SubmissionError(f"duplicate rank: {r.rank}")
        seen_ranks.add(r.rank)

    # Re-sort by (rank ascending). Tie-break inside equal scores has already
    # been resolved by the ranker; we trust it but verify monotonicity here.
    rows = sorted(rows, key=lambda x: x.rank)
    for a, b in zip(rows, rows[1:], strict=False):
        if a.score < b.score:
            raise SubmissionError(
                f"score must be non-increasing: rank {a.rank}={a.score} < rank {b.rank}={b.score}"
            )
        if a.score == b.score and a.candidate_id > b.candidate_id:
            raise SubmissionError(
                f"tie-break violation at ranks {a.rank}/{b.rank}: "
                f"equal score requires candidate_id ascending"
            )
    return rows


def write_submission(
    rows: Iterable[RankedCandidate],
    path: str | Path,
    *,
    strict: bool = True,
) -> Path:
    """Validate (when ``strict``) + write the top-K CSV.

    ``strict=True`` (the default) enforces every invariant the official
    ``validate_submission.py`` checks - this is what we use for the real
    100-row submission. ``strict=False`` is for debugging / smoke runs on
    small samples (e.g. the 50-row fixture) where we just want to inspect
    the shortlist locally.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    materialised = list(rows)
    if strict:
        materialised = _enforce_invariants(materialised)
    else:
        materialised = sorted(materialised, key=lambda x: x.rank)

    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writerow(HEADER)
        for r in materialised:
            # Clamp score to 4 decimals to keep the CSV diff-friendly.
            writer.writerow(
                [r.candidate_id, r.rank, f"{r.score:.4f}", r.reasoning.replace("\n", " ").strip()]
            )
    return out
