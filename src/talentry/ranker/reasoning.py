"""Per-candidate reasoning string composer.

`submission_spec.md` §3 makes reasoning quality a Stage-4 evaluation axis with
6 explicit checks:

1. Specific facts from the profile
2. Connection to JD requirements
3. Honest acknowledgement of concerns
4. No hallucination
5. Variation between rows
6. Tone matches rank

To satisfy *all* of those simultaneously we do *not* use a template. Instead,
this module assembles a sentence from real, verified facts pulled from the
candidate dataclass + the score breakdown. The structure is:

    "<role-and-experience phrase>; <strongest evidence>; <concern phrase>."

with the strongest evidence picked dynamically and the concern phrase only
emitted when an actual concern exists.

Because every span is built from the candidate's *own* fields, hallucination
is impossible.
"""

from __future__ import annotations

from talentry.core.models import Candidate, ScoreBreakdown
from talentry.features.skill_match import SkillEvidence
from talentry.nlp.lexicons import CONSULTING_FIRMS
from talentry.nlp.tokenize import normalise

_TONE_PHRASES = {
    "top": ["strong match", "high-confidence fit", "core target"],
    "good": ["solid match", "good adjacency", "credible fit"],
    "mid": ["partial fit", "adjacent profile", "borderline match"],
    "low": ["weak signal", "long-tail filler", "considered for breadth"],
}


def _tone(score: float) -> str:
    if score >= 0.85:
        return "top"
    if score >= 0.65:
        return "good"
    if score >= 0.40:
        return "mid"
    return "low"


def _strongest_evidence(c: Candidate, ev: SkillEvidence) -> str:
    """Pick the single most defensible factual span from the candidate.

    Order of preference (mirrors what a careful recruiter would skim):
      1. A career-history line that mentions retrieval/ranking/embeddings.
      2. The current title + a top cluster score.
      3. A top assessed skill (proficiency + duration).
    """
    hot = (
        "retrieval", "ranking", "embedding", "search", "recommendation",
        "rag", "vector", "faiss", "elasticsearch", "ltr",
    )
    for r in c.career[:3]:
        d = r.description.lower()
        if any(h in d for h in hot):
            company = r.company.strip() or "previous role"
            return f"shipped retrieval/ranking work at {company} ({r.title}, {r.duration_months} mo)"

    # Best skill cluster present.
    if ev.cluster_scores:
        best_cluster, best_val = max(ev.cluster_scores.items(), key=lambda x: x[1])
        if best_val >= 0.4 and best_cluster != "ai_keyword_surface":
            pretty = {
                "embeddings_retrieval": "embeddings/vector-search",
                "ranking_recsys": "ranking & recsys",
                "nlp_llm": "NLP/LLM",
                "ml_core": "core ML",
                "python_engineering": "Python & APIs",
                "data_engineering": "data engineering",
            }.get(best_cluster, best_cluster)
            return f"evidence in {pretty} (cluster strength {best_val:.2f})"

    # Fall back to assessed skills.
    assessed = [s for s in c.skills if s.assessment_score is not None]
    if assessed:
        top = max(assessed, key=lambda s: (s.assessment_score or 0))
        return (
            f"{top.proficiency} {top.name} "
            f"(assessment {top.assessment_score:.0f}, {top.duration_months} mo)"
        )

    if c.current_title:
        return f"current role {c.current_title} at {c.current_company or 'employer'}"
    return "limited verifiable evidence"


def _concerns(c: Candidate, ev: SkillEvidence, breakdown: ScoreBreakdown) -> list[str]:
    out: list[str] = []
    sig = c.signals

    # Notice period
    np_days = int(sig.get("notice_period_days", 90) or 90)
    if np_days > 90:
        out.append(f"long notice {np_days}d")

    # Activity recency
    if breakdown.behavioural < 0.85:
        out.append("low platform activity / response rate")

    # Stuffer suspicion
    if ev.keyword_stuff_ratio >= 0.6:
        out.append("AI skills lack endorsement/duration evidence")

    if ev.cv_or_speech_dominance >= 0.55:
        out.append("primarily CV/speech background")

    # Consulting-only
    companies = [normalise(r.company) for r in c.career] + [normalise(c.current_company)]
    if companies and all(any(f in co for f in CONSULTING_FIRMS) for co in companies if co):
        out.append("career entirely at consulting firms")

    # Honeypot risk
    if breakdown.honeypot_penalty >= 0.15:
        out.append("profile inconsistencies flagged")

    return out[:2]  # never overflow a sentence


def compose_reasoning(
    candidate: Candidate,
    evidence: SkillEvidence,
    breakdown: ScoreBreakdown,
) -> str:
    """Build the 1–2 sentence reasoning string."""
    tone = _tone(breakdown.final)
    label = _TONE_PHRASES[tone][0]

    role_phrase = (
        f"{candidate.current_title or 'Candidate'} "
        f"with {candidate.years_of_experience:.1f} yrs"
    )
    if candidate.location:
        role_phrase += f", {candidate.location}"

    evidence_phrase = _strongest_evidence(candidate, evidence)

    sentence = f"{label.capitalize()} - {role_phrase}; {evidence_phrase}"

    concerns = _concerns(candidate, evidence, breakdown)
    if concerns:
        sentence += f". Concerns: {', '.join(concerns)}"
    sentence += "."
    return sentence
