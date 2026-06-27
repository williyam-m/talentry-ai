"""Honeypot detection - additive penalty in [0, 0.5].

From `submission_spec` §7:

    The dataset contains a small number (~80) of honeypot candidates with
    subtly impossible profiles (e.g., 8 years of experience at a company
    founded 3 years ago; 'expert' proficiency in 10 skills with 0 years used).
    These are forced to relevance tier 0 in the ground truth.

We don't try to label them perfectly - we just don't want them in the top-10
(which would also disqualify us via the 10% honeypot rate filter at Stage 3).
The penalty is **additive** (not a multiplier), so it can knock a top-shelf
score off the leaderboard.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from talentry.core.models import Candidate

_HIGH_PROF = {"expert", "advanced"}


def _parse_year(s: str | None) -> int | None:
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").year
    except ValueError:
        try:
            return int(str(s)[:4])
        except ValueError:
            return None


def honeypot_score(c: Candidate) -> float:
    """Return a penalty in [0, 0.5]. Higher = more suspicious."""
    penalty = 0.0

    # 1. Career-months overflow: sum(career) far exceeds years_of_experience.
    total_months = sum(int(r.duration_months or 0) for r in c.career)
    declared_months = int(round((c.years_of_experience or 0.0) * 12))
    if declared_months > 0 and total_months - declared_months >= 24:
        penalty += 0.18

    # 2. High-confidence skill claims with no evidence at all.
    suspicious = 0
    for s in c.skills:
        if s.proficiency in _HIGH_PROF and s.endorsements == 0 and s.duration_months <= 2:
            suspicious += 1
    if suspicious >= 3:
        penalty += 0.15

    # 3. Salary band inversion.
    sal = c.signals.get("expected_salary_range_inr_lpa") or {}
    smin = sal.get("min")
    smax = sal.get("max")
    if isinstance(smin, (int, float)) and isinstance(smax, (int, float)) and smin > smax > 0:
        penalty += 0.08

    # 4. signup_date *after* last_active_date.
    su = c.signals.get("signup_date")
    la = c.signals.get("last_active_date")
    try:
        if su and la and str(su) > str(la):  # ISO dates compare lexicographically
            penalty += 0.04
    except Exception:
        pass

    # 5. is_current=True on a role whose start_date is in the future relative
    # to all education end years - weak signal but cheap.
    cur_starts = [_parse_year(r.start_date) for r in c.career if r.is_current]
    edu_ends = [e.end_year for e in c.education if e.end_year]
    if cur_starts and edu_ends and max(edu_ends) > max(filter(None, cur_starts or [0]), default=0) + 1:
        # Edu finishes well after they "started" current job? Mildly weird.
        penalty += 0.03

    # 6. is_current True on more than one role (impossible).
    if sum(1 for r in c.career if r.is_current) > 1:
        penalty += 0.10

    return min(0.5, penalty)
