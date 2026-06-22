"""End-to-end ranking pipeline.

``rank_candidates`` is the single function the CLI, API and HuggingFace Space
all sit on top of. It is **deterministic** (no random state, no clock-dependent
behaviour aside from optional ``reference_date``) so the Stage 3 sandbox
reproduces our submission bit-for-bit.

Pipeline:

    1. Build per-candidate text blobs.
    2. Build the hybrid BM25 + TF-IDF index over those blobs.
    3. For each candidate:
         a. Compute role/career signals.
         b. Compute skill evidence.
         c. Compute behavioural multiplier + honeypot penalty.
         d. Compose ScoreBreakdown.
    4. Sort by (final score desc, candidate_id asc).
    5. Take top-K (default 100), compose reasoning, build RankedCandidate.

Memory budget: the entire pipeline keeps Candidate objects + the TF-IDF
sparse matrix in RAM. On the 100K dataset this fits comfortably under 4 GB.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from datetime import date

from talentry.core.models import Candidate, JobRequirements, RankedCandidate
from talentry.features.builder import build_role_signals, build_text_blob
from talentry.features.skill_match import score_skill_evidence
from talentry.ranker.reasoning import compose_reasoning
from talentry.ranker.scorer import (
    compose_final,
    experience_band_score,
    location_score,
    skill_component_score,
    title_alignment_score,
)
from talentry.ranker.semantic import build_index
from talentry.signals.behavioural import behavioural_multiplier
from talentry.signals.honeypot import honeypot_score

_LOG = logging.getLogger("talentry.ranker")


def rank_candidates(
    candidates: Iterable[Candidate],
    jd: JobRequirements,
    *,
    top_k: int = 100,
    reference_date: date | None = None,
    progress: bool = False,
) -> list[RankedCandidate]:
    """Rank candidates against the JD and return the top-K shortlist.

    Parameters
    ----------
    candidates:
        Iterable of :class:`Candidate` objects (typically loaded via
        :func:`talentry.io.candidates.load_candidates`).
    jd:
        Parsed job description (see :func:`talentry.ranker.parse_job_description`).
    top_k:
        Number of candidates in the final shortlist. The hackathon requires 100.
    reference_date:
        "Today" for behavioural recency calculations. Defaults to the system
        date — explicitly settable for reproducible tests.
    progress:
        If True, log a progress message every ~10K candidates.
    """
    materialised: list[Candidate] = list(candidates)
    n = len(materialised)
    if n == 0:
        return []

    t0 = time.perf_counter()

    # ── Stage 1: text blobs ────────────────────────────────────────────────
    for c in materialised:
        build_text_blob(c)
    _LOG.info("[talentry] built text blobs for %d candidates in %.2fs", n, time.perf_counter() - t0)

    # ── Stage 2: hybrid index ─────────────────────────────────────────────
    t1 = time.perf_counter()
    index = build_index(materialised)
    semantic_scores = index.score(jd.raw_text)
    _LOG.info(
        "[talentry] built hybrid BM25+TF-IDF index in %.2fs (avg=%.3f)",
        time.perf_counter() - t1,
        sum(semantic_scores.values()) / max(1, len(semantic_scores)),
    )

    # ── Stage 3: per-candidate scoring ─────────────────────────────────────
    t2 = time.perf_counter()
    scored: list[tuple[Candidate, object, float, object]] = []
    # Pre-compute per-candidate evidence + breakdown.
    for i, c in enumerate(materialised):
        role_sigs = build_role_signals(c)
        evidence = score_skill_evidence(c, jd.must_have_skills)
        beh = behavioural_multiplier(c.signals, reference_date=reference_date)
        hp = honeypot_score(c)

        breakdown = compose_final(
            title_alignment=title_alignment_score(role_sigs),
            semantic_fit=semantic_scores.get(c.candidate_id, 0.0),
            skill_evidence=skill_component_score(evidence),
            experience_band=experience_band_score(c.years_of_experience, jd),
            location=location_score(c, jd),
            behavioural=beh,
            honeypot_penalty=hp,
        )
        scored.append((c, evidence, breakdown.final, breakdown))

        if progress and (i + 1) % 10_000 == 0:
            _LOG.info("[talentry] scored %d / %d candidates", i + 1, n)
    _LOG.info("[talentry] scored all candidates in %.2fs", time.perf_counter() - t2)

    # ── Stage 4: sort + top-K + reasoning ──────────────────────────────────
    # Tie-break: candidate_id ascending so the writer's invariants hold.
    scored.sort(key=lambda x: (-x[2], x[0].candidate_id))
    top = scored[:top_k]

    out: list[RankedCandidate] = []
    for rank, (c, ev, score, breakdown) in enumerate(top, start=1):
        reasoning = compose_reasoning(c, ev, breakdown)
        out.append(
            RankedCandidate(
                candidate_id=c.candidate_id,
                rank=rank,
                score=round(score, 4),
                reasoning=reasoning,
                breakdown=breakdown,
            )
        )

    _LOG.info(
        "[talentry] produced top-%d in %.2fs total (over %d candidates)",
        len(out),
        time.perf_counter() - t0,
        n,
    )
    return out
