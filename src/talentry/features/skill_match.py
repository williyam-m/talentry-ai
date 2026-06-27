"""Skill evidence scoring - the anti-keyword-stuffer core of the ranker.

Why is this a separate module?

The JD is *explicit* about the trap built into the dataset:

    A candidate who has all the AI keywords listed as skills but whose title is
    'Marketing Manager' is not a fit, no matter how perfect their skill list
    looks.

If we score skills as a flat keyword match (skill name in JD ⇒ +1) we will
rank stuffers in our top-10 and disqualify ourselves at Stage 3 via the
honeypot filter. So instead we score *evidence* per claimed skill:

    evidence = f(endorsements, duration_months, proficiency, assessment_score)

…then aggregate per skill-cluster. A "LangChain" claim with zero endorsements,
3 months of usage and no assessment is worth essentially nothing.

Returns are bounded in [0, 1] per cluster so the downstream linear combination
remains interpretable.
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from talentry.core.models import Candidate, Skill
from talentry.nlp.lexicons import (
    CV_ONLY_SKILLS,
    SKILL_CLUSTERS,
    SPEECH_ONLY_SKILLS,
)
from talentry.nlp.tokenize import normalise

# Proficiency → base trust multiplier.
_PROFICIENCY_WEIGHT: dict[str, float] = {
    "beginner": 0.25,
    "intermediate": 0.55,
    "advanced": 0.85,
    "expert": 1.0,
}

# Skill-name fuzzy threshold for lexical matching ("postgresql" ↔ "postgres").
_FUZZY_THRESHOLD = 88


@dataclass(slots=True)
class SkillEvidence:
    """Aggregated, evidence-weighted skill scoring for one candidate."""

    cluster_scores: dict[str, float]
    must_have_hits: list[str]
    must_have_misses: list[str]
    cv_or_speech_dominance: float  # 0..1, share of *evidence* attributable to CV/speech only
    keyword_stuff_ratio: float  # 0..1, share of cluster hits that are pure-keyword (no evidence)

    @property
    def overall(self) -> float:
        """Mean of cluster scores - a fast scalar summary."""
        if not self.cluster_scores:
            return 0.0
        return sum(self.cluster_scores.values()) / len(self.cluster_scores)


def _skill_trust(skill: Skill) -> float:
    """Return a [0,1] trust score for a single claimed skill.

    A keyword-stuffer typically posts `expert` claims with 0-3 endorsements
    and 0-6 months of usage. Real practitioners have *long* duration and
    accumulate endorsements. We make those facts numeric.
    """
    prof = _PROFICIENCY_WEIGHT.get(skill.proficiency, 0.4)

    # Endorsements saturate around 50 (per the dataset's natural max ≈ 60).
    endorse = min(skill.endorsements, 50) / 50.0

    # Duration saturates around 36 months.
    dur = min(skill.duration_months, 36) / 36.0

    # Assessment score (if present) is the strongest signal.
    if skill.assessment_score is not None:
        assess = skill.assessment_score / 100.0
        return min(1.0, 0.40 * prof + 0.20 * endorse + 0.10 * dur + 0.30 * assess)
    return min(1.0, 0.55 * prof + 0.25 * endorse + 0.20 * dur)


def _matches_cluster(skill_name: str, cluster: list[str]) -> str | None:
    """Return the cluster member matched (or None) using fuzzy comparison."""
    n = normalise(skill_name)
    if not n:
        return None
    for member in cluster:
        m = normalise(member)
        if m in n or n in m:
            return member
        if fuzz.ratio(n, m) >= _FUZZY_THRESHOLD:
            return member
    return None


def score_skill_evidence(c: Candidate, must_have: list[str]) -> SkillEvidence:
    """Compute :class:`SkillEvidence` for one candidate.

    `must_have` is the JD's "things you absolutely need" list.
    """
    cluster_total: dict[str, float] = dict.fromkeys(SKILL_CLUSTERS.keys(), 0.0)
    cluster_count: dict[str, int] = dict.fromkeys(SKILL_CLUSTERS.keys(), 0)

    cv_trust = 0.0
    speech_trust = 0.0
    total_trust = 1e-9
    stuff_hits = 0
    stuff_total = 0

    for s in c.skills:
        t = _skill_trust(s)
        total_trust += t

        sn = normalise(s.name)
        if sn in CV_ONLY_SKILLS:
            cv_trust += t
        if sn in SPEECH_ONLY_SKILLS:
            speech_trust += t

        # Stuffer probe runs independently of cluster assignment: any AI
        # keyword surface claim contributes to the stuff ratio if the
        # candidate posted it with high proficiency but trivial evidence.
        # "Trivial evidence" = essentially zero endorsements AND short usage,
        # regardless of the proficiency label they self-assigned.
        if _matches_cluster(s.name, SKILL_CLUSTERS["ai_keyword_surface"]):
            stuff_total += 1
            looks_padded = (
                s.proficiency in {"advanced", "expert"}
                and s.endorsements <= 2
                and s.duration_months <= 6
                and s.assessment_score is None
            )
            if looks_padded or t < 0.40:
                stuff_hits += 1

        # For cluster contribution we still pick the most specific (first)
        # cluster so we don't double-count one skill.
        for cluster_name, members in SKILL_CLUSTERS.items():
            if cluster_name == "ai_keyword_surface":
                continue
            if _matches_cluster(s.name, members):
                cluster_total[cluster_name] += t
                cluster_count[cluster_name] += 1
                break

    # Normalise each cluster to [0,1]. We divide by the smaller of
    # (cluster_size, 4) so a candidate doesn't need to list 12 retrieval skills
    # to score a perfect 1.0 on that cluster.
    cluster_scores: dict[str, float] = {}
    for cluster_name, total in cluster_total.items():
        target = min(len(SKILL_CLUSTERS[cluster_name]), 4)
        cluster_scores[cluster_name] = min(1.0, total / target) if target else 0.0

    # Must-have hit / miss diagnostics (free strings - used by the reasoning
    # composer).
    must_hits: list[str] = []
    must_misses: list[str] = []
    for need in must_have:
        if any(_matches_cluster(s.name, [need]) for s in c.skills):
            must_hits.append(need)
        else:
            must_misses.append(need)

    cv_or_speech_dominance = (cv_trust + speech_trust) / total_trust
    keyword_stuff_ratio = (stuff_hits / stuff_total) if stuff_total else 0.0

    return SkillEvidence(
        cluster_scores=cluster_scores,
        must_have_hits=must_hits,
        must_have_misses=must_misses,
        cv_or_speech_dominance=min(1.0, cv_or_speech_dominance),
        keyword_stuff_ratio=keyword_stuff_ratio,
    )
