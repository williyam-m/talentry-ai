"""Domain models used across the Talentry pipeline.

These are intentionally *plain* dataclasses (no pydantic, no third-party deps)
so that:

* the public API stays trivial to serialise/deserialise to JSON;
* the ranking hot-path stays allocation-cheap on a CPU laptop;
* the schema mirrors the official Redrob `candidate_schema.json` 1:1 and
  therefore documents itself for future maintainers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Skill:
    """A single skill claim on a candidate's profile."""

    name: str
    proficiency: str = "beginner"
    endorsements: int = 0
    duration_months: int = 0
    assessment_score: float | None = None  # 0-100, from redrob_signals if present


@dataclass(slots=True)
class CareerEntry:
    """One role in a candidate's career history."""

    company: str
    title: str
    start_date: str
    end_date: str | None
    duration_months: int
    is_current: bool
    industry: str
    company_size: str
    description: str


@dataclass(slots=True)
class EducationEntry:
    institution: str
    degree: str
    field_of_study: str
    start_year: int
    end_year: int
    grade: str | None = None
    tier: str = "unknown"


@dataclass(slots=True)
class Candidate:
    """The flattened view of one record from `candidates.jsonl`.

    Only the fields the ranker actually consumes are materialised — the
    rest live in `raw` so that downstream consumers (e.g. the reasoning
    composer) can pull them on demand without us paying for them per row.
    """

    candidate_id: str
    name: str
    headline: str
    summary: str
    location: str
    country: str
    years_of_experience: float
    current_title: str
    current_company: str
    current_company_size: str
    current_industry: str
    career: list[CareerEntry] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    signals: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    # Pre-computed search text — set by the indexing layer.
    text_blob: str = ""


@dataclass(slots=True)
class JobRequirements:
    """A structured view of the job description used by the scorer.

    `JD parsing` in Talentry is rule + lexicon based (zero LLM at ranking
    time) but the *output* of parsing is this dataclass so the rest of
    the system never re-reads the raw JD text.
    """

    title: str
    role_family: str
    seniority: str  # "junior" | "mid" | "senior" | "staff+"
    min_years: float
    max_years: float
    must_have_skills: list[str] = field(default_factory=list)
    nice_to_have_skills: list[str] = field(default_factory=list)
    disqualifier_skills: list[str] = field(default_factory=list)
    preferred_locations: list[str] = field(default_factory=list)
    relocation_friendly_locations: list[str] = field(default_factory=list)
    preferred_notice_days: int = 30
    soft_notice_days: int = 90
    consulting_firms_penalised: list[str] = field(default_factory=list)
    product_company_bonus: bool = True
    behavioural_priors: dict[str, float] = field(default_factory=dict)
    raw_text: str = ""


@dataclass(slots=True)
class ScoreBreakdown:
    """Per-candidate, per-component score for full transparency."""

    title_alignment: float = 0.0
    semantic_fit: float = 0.0
    skill_evidence: float = 0.0
    experience_band: float = 0.0
    location: float = 0.0
    behavioural: float = 1.0  # multiplier in [0,1.2]
    honeypot_penalty: float = 0.0  # subtractive
    final: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "title_alignment": round(self.title_alignment, 4),
            "semantic_fit": round(self.semantic_fit, 4),
            "skill_evidence": round(self.skill_evidence, 4),
            "experience_band": round(self.experience_band, 4),
            "location": round(self.location, 4),
            "behavioural": round(self.behavioural, 4),
            "honeypot_penalty": round(self.honeypot_penalty, 4),
            "final": round(self.final, 4),
        }


@dataclass(slots=True)
class RankedCandidate:
    """One row of the final shortlist."""

    candidate_id: str
    rank: int
    score: float
    reasoning: str
    breakdown: ScoreBreakdown
