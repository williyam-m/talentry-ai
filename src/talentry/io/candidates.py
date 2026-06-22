"""Candidate I/O — load JSONL (plain or gzipped) into our domain models.

We keep two surfaces:

* :func:`iter_candidate_records` — yields raw ``dict`` payloads, one per line.
  This is useful for streaming workflows where the caller wants to materialise
  only what they need (e.g. the UI showing 50 candidates).
* :func:`load_candidates` — fully materialises into :class:`Candidate` objects
  and is the entry point used by the ranker.

Both are tolerant of:
* gzipped (`.jsonl.gz`) or plain (`.jsonl` / `.json`) input;
* a top-level JSON array *or* line-delimited JSON;
* missing optional fields (which the schema marks as optional).
"""

from __future__ import annotations

import gzip
import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import orjson

from talentry.core.models import Candidate, CareerEntry, EducationEntry, Skill

JSONLike = dict[str, Any]


def _open_text(path: Path) -> io.TextIOBase:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")  # type: ignore[return-value]
    return path.open("r", encoding="utf-8")


def iter_candidate_records(path: str | Path) -> Iterator[JSONLike]:
    """Yield raw candidate dicts from a JSONL / JSON / gzip-of-JSONL file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)

    with _open_text(p) as fh:
        first = fh.read(1)
        fh.seek(0)
        if first == "[":  # JSON array
            data = json.load(fh)
            for rec in data:
                yield rec
            return
        # JSON Lines
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield orjson.loads(line)


def _coerce_skill(d: JSONLike, assessment_scores: dict[str, float]) -> Skill:
    name = str(d.get("name", "")).strip()
    return Skill(
        name=name,
        proficiency=str(d.get("proficiency", "beginner")).lower(),
        endorsements=int(d.get("endorsements", 0) or 0),
        duration_months=int(d.get("duration_months", 0) or 0),
        assessment_score=assessment_scores.get(name),
    )


def _coerce_career(d: JSONLike) -> CareerEntry:
    return CareerEntry(
        company=str(d.get("company", "")),
        title=str(d.get("title", "")),
        start_date=str(d.get("start_date", "")),
        end_date=d.get("end_date"),
        duration_months=int(d.get("duration_months", 0) or 0),
        is_current=bool(d.get("is_current", False)),
        industry=str(d.get("industry", "")),
        company_size=str(d.get("company_size", "")),
        description=str(d.get("description", "")),
    )


def _coerce_education(d: JSONLike) -> EducationEntry:
    return EducationEntry(
        institution=str(d.get("institution", "")),
        degree=str(d.get("degree", "")),
        field_of_study=str(d.get("field_of_study", "")),
        start_year=int(d.get("start_year", 0) or 0),
        end_year=int(d.get("end_year", 0) or 0),
        grade=d.get("grade"),
        tier=str(d.get("tier", "unknown")),
    )


def to_candidate(raw: JSONLike) -> Candidate:
    """Coerce a single raw record into a :class:`Candidate`."""
    profile = raw.get("profile", {}) or {}
    signals = raw.get("redrob_signals", {}) or {}
    assessment = signals.get("skill_assessment_scores", {}) or {}

    return Candidate(
        candidate_id=str(raw["candidate_id"]),
        name=str(profile.get("anonymized_name", "")),
        headline=str(profile.get("headline", "")),
        summary=str(profile.get("summary", "")),
        location=str(profile.get("location", "")),
        country=str(profile.get("country", "")),
        years_of_experience=float(profile.get("years_of_experience", 0.0) or 0.0),
        current_title=str(profile.get("current_title", "")),
        current_company=str(profile.get("current_company", "")),
        current_company_size=str(profile.get("current_company_size", "")),
        current_industry=str(profile.get("current_industry", "")),
        career=[_coerce_career(c) for c in (raw.get("career_history") or [])],
        education=[_coerce_education(e) for e in (raw.get("education") or [])],
        skills=[_coerce_skill(s, assessment) for s in (raw.get("skills") or [])],
        signals=signals,
        raw=raw,
    )


def load_candidates(path: str | Path, *, limit: int | None = None) -> list[Candidate]:
    """Materialise all (or `limit`) candidates from disk into memory."""
    out: list[Candidate] = []
    for i, raw in enumerate(iter_candidate_records(path)):
        if limit is not None and i >= limit:
            break
        out.append(to_candidate(raw))
    return out
