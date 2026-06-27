"""Per-candidate scoring components and final composition.

The scorer is the place where the JD is *actually* translated into a number.
We keep it open-coded (no model weights, no LightGBM) for three reasons:

1. **Reproducibility at Stage 3.** The Redrob organisers will rerun our
   ranker in a sandboxed Docker. A pure-Python scorer with explicit constants
   reproduces bit-for-bit; an LGBM model would need a serialised artifact and
   matching library versions.
2. **Explainability at Stage 4.** Every component is named, bounded, and
   referenced by the reasoning composer.
3. **Defensibility at Stage 5.** We can defend each constant by citing the
   line of the JD that motivated it.

Composition:
    final = w_title * title_alignment
          + w_semantic * semantic_fit
          + w_skill * skill_evidence
          + w_exp * experience_band
          + w_loc * location
    final *= behavioural_multiplier          # in [0.55, 1.20]
    final -= honeypot_penalty                # in [0, 0.5]
    final  = clip(final, -0.5, 1.5)
"""

from __future__ import annotations

from typing import Any

from talentry.core.models import Candidate, JobRequirements, ScoreBreakdown
from talentry.features.skill_match import SkillEvidence
from talentry.nlp.lexicons import (
    PREFERRED_LOCATIONS,
    TIER1_INDIA_LOCATIONS,
)
from talentry.nlp.tokenize import normalise

# Component weights. These sum to 1.0 on the linear-combination part so the
# pre-multiplier score is bounded in [-1, 1].
W_TITLE = 0.32
W_SEMANTIC = 0.22
W_SKILL = 0.28
W_EXP = 0.12
W_LOC = 0.06
assert abs(W_TITLE + W_SEMANTIC + W_SKILL + W_EXP + W_LOC - 1.0) < 1e-9


def title_alignment_score(role_signals: dict[str, Any]) -> float:
    """Score a candidate's title/career trajectory against the JD's role family.

    Returns a value in roughly [-1, 1]. The negative tail catches the JD's
    explicit non-targets (Marketing Manager, etc.).
    """
    cur = float(role_signals.get("current_family_score", 0.0))
    avg = float(role_signals.get("avg_recent_family_score", 0.0))

    base = 0.7 * cur + 0.3 * avg  # in [-1, 3]
    base = base / 3.0  # → [-1/3, 1]

    if role_signals.get("only_consulting"):
        base -= 0.40  # JD: "People who have only worked at consulting firms"
    if role_signals.get("pure_management_track"):
        base -= 0.20  # JD: "this role writes code"
    if role_signals.get("has_product_company"):
        base += 0.10  # JD: "applied ML at product companies (not pure services)"

    return max(-1.0, min(1.0, base))


def experience_band_score(years: float, jd: JobRequirements) -> float:
    """Triangular score, 1.0 inside [min, max], soft-decaying outside.

    The JD literally says "5-9 is a range, not a requirement … we'll seriously
    consider candidates outside the band if other signals are strong" - hence
    the soft decay rather than a hard cutoff.
    """
    lo, hi = jd.min_years, jd.max_years
    if lo <= years <= hi:
        return 1.0
    if years < lo:
        # Decays to 0 at ~half the lower bound.
        return max(0.0, years / lo)
    # years > hi
    over = years - hi
    return max(0.0, 1.0 - 0.10 * over)


def location_score(candidate: Candidate, jd: JobRequirements) -> float:
    """Reward proximity to Pune/Noida, partial credit for tier-1 India.

    The JD: "Outside India: case-by-case, but we don't sponsor work visas."
    """
    loc = normalise(candidate.location)
    country = normalise(candidate.country)

    in_country = "india" in country
    in_preferred = any(p in loc for p in PREFERRED_LOCATIONS)
    in_tier1 = any(p in loc for p in TIER1_INDIA_LOCATIONS)

    willing = bool(candidate.signals.get("willing_to_relocate"))

    if in_preferred:
        return 1.0
    if in_tier1:
        return 0.85 if willing else 0.75
    if in_country:
        return 0.65 if willing else 0.45
    # Outside India
    return 0.30 if willing else 0.10


def skill_component_score(
    evidence: SkillEvidence,
    *,
    cv_or_speech_penalty_threshold: float = 0.55,
) -> float:
    """Combine cluster scores into one [0,1] number.

    Cluster weights mirror the JD's "absolutely need" vs "nice to have".
    """
    cs = evidence.cluster_scores
    base = (
        0.30 * cs.get("embeddings_retrieval", 0.0)
        + 0.20 * cs.get("ranking_recsys", 0.0)
        + 0.20 * cs.get("nlp_llm", 0.0)
        + 0.15 * cs.get("ml_core", 0.0)
        + 0.10 * cs.get("python_engineering", 0.0)
        + 0.05 * cs.get("data_engineering", 0.0)
    )
    # Hard penalise candidates whose evidence is almost entirely CV/speech.
    if evidence.cv_or_speech_dominance >= cv_or_speech_penalty_threshold:
        base *= 0.55

    # Stuffer penalty: if every AI keyword they list has trivial evidence,
    # discount the whole skill score.
    if evidence.keyword_stuff_ratio >= 0.7:
        base *= 0.65

    return min(1.0, base)


def compose_final(
    *,
    title_alignment: float,
    semantic_fit: float,
    skill_evidence: float,
    experience_band: float,
    location: float,
    behavioural: float,
    honeypot_penalty: float,
) -> ScoreBreakdown:
    """Apply the documented composition rule and return :class:`ScoreBreakdown`."""
    linear = (
        W_TITLE * title_alignment
        + W_SEMANTIC * semantic_fit
        + W_SKILL * skill_evidence
        + W_EXP * experience_band
        + W_LOC * location
    )
    final = linear * behavioural - honeypot_penalty
    final = max(-0.5, min(1.5, final))

    return ScoreBreakdown(
        title_alignment=title_alignment,
        semantic_fit=semantic_fit,
        skill_evidence=skill_evidence,
        experience_band=experience_band,
        location=location,
        behavioural=behavioural,
        honeypot_penalty=honeypot_penalty,
        final=final,
    )
