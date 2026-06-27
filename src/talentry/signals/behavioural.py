"""Compute the behavioural availability multiplier from Redrob signals.

The JD is explicit:

    A perfect-on-paper candidate who hasn't logged in for 6 months and has a
    5% recruiter response rate is, for hiring purposes, not actually available.
    Down-weight them appropriately.

We compute a *multiplier* in [0.55, 1.20] applied on top of the linearly
combined skill/title/experience scores. We never zero a candidate out on
behaviour alone - a real recruiter can always call them - but a recruiter who
won't respond is worth materially less than one who will.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _safe_date(s: Any) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _days_since(d: date | None, reference: date) -> int | None:
    if d is None:
        return None
    return (reference - d).days


def behavioural_multiplier(
    signals: dict[str, Any],
    *,
    reference_date: date | None = None,
) -> float:
    """Return a multiplier in [0.55, 1.20].

    Components, each contributing additively to a base of 1.0 (clipped):

    * Activity recency  - last_active within 60 days bumps, > 180 penalises
    * Recruiter response rate
    * Interview completion rate
    * Open-to-work flag + verified contacts
    * Notice period proximity to the JD's <30-day preference
    """
    reference_date = reference_date or date.today()

    # Activity recency
    last_active = _safe_date(signals.get("last_active_date"))
    days = _days_since(last_active, reference_date)
    if days is None:
        recency = 0.0
    elif days <= 30:
        recency = 0.12
    elif days <= 90:
        recency = 0.05
    elif days <= 180:
        recency = -0.05
    else:
        recency = -0.20

    # Recruiter response rate (0..1, JD-priority signal).
    rr = float(signals.get("recruiter_response_rate", 0.0) or 0.0)
    response = (rr - 0.40) * 0.30  # neutral at 40%, +0.18 at 100%, -0.12 at 0%

    # Interview completion - they actually show up.
    icr = float(signals.get("interview_completion_rate", 0.0) or 0.0)
    interview = (icr - 0.50) * 0.15

    # Open-to-work + verification.
    otw = 0.05 if signals.get("open_to_work_flag") else -0.02
    verified = 0.0
    if signals.get("verified_email"):
        verified += 0.015
    if signals.get("verified_phone"):
        verified += 0.015
    if signals.get("linkedin_connected"):
        verified += 0.02

    # Notice period (lower is better; JD prefers <30d).
    np_days = float(signals.get("notice_period_days", 90) or 90)
    if np_days <= 30:
        notice = 0.05
    elif np_days <= 60:
        notice = 0.0
    elif np_days <= 90:
        notice = -0.04
    else:
        notice = -0.08

    # Saturated activity bonus - search appearances + saved-by-recruiters say
    # the platform's own ranker thinks they're a hot candidate.
    saved = min(float(signals.get("saved_by_recruiters_30d", 0) or 0), 20) / 20.0
    activity_bonus = 0.05 * saved

    score = 1.0 + recency + response + interview + otw + verified + notice + activity_bonus
    return max(0.55, min(1.20, score))
