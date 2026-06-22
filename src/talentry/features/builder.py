"""Feature builders: per-candidate text blobs and role signals.

These are the *only* per-candidate features used for hot-path scoring. We keep
them tiny and pure so they're trivially testable and cheap at 100K scale.
"""

from __future__ import annotations

from talentry.core.models import Candidate
from talentry.nlp.lexicons import (
    CONSULTING_FIRMS,
    PRODUCT_COMPANY_HINTS,
    ROLE_KEYWORD_INDEX,
)
from talentry.nlp.tokenize import normalise


def build_text_blob(c: Candidate) -> str:
    """Compose the searchable text used by BM25 / TF-IDF.

    We deliberately *upweight* the parts of the profile that the JD says are
    most signal-bearing — career-history descriptions and the summary — by
    repeating them. BM25 saturates so the duplication just nudges term
    frequency in the right direction without breaking IDF.
    """
    parts: list[str] = [
        c.headline,
        c.summary, c.summary,  # 2x — JD: read between the lines of the summary
        c.current_title, c.current_title,
        c.current_industry,
    ]
    for entry in c.career:
        parts.append(entry.title)
        parts.append(entry.description)
        parts.append(entry.description)  # 2x — career description = where IR/RAG hides
        parts.append(entry.industry)
    for s in c.skills:
        parts.append(s.name)
    for e in c.education:
        parts.append(f"{e.degree} {e.field_of_study} {e.institution}")
    blob = " ".join(p for p in parts if p)
    c.text_blob = blob
    return blob


def _match_role(title: str) -> tuple[str, float]:
    """Map a free-text title to (family, family_score). Longest-match wins."""
    if not title:
        return ("unknown", 0.0)
    t = normalise(title)
    best: tuple[str, float, int] = ("unknown", 0.0, 0)  # (family, score, kw_len)
    for kw, (fam, score) in ROLE_KEYWORD_INDEX.items():
        if kw in t and len(kw) > best[2]:
            best = (fam, score, len(kw))
    return best[0], best[1]


def build_role_signals(c: Candidate) -> dict[str, float | str | bool]:
    """Derive role-trajectory features used by the title/career alignment scorer.

    Returns a flat dict so callers don't pay attribute-access overhead in the
    hot loop.
    """
    current_family, current_score = _match_role(c.current_title)

    # Look at the last (up to) 3 roles for trajectory analysis.
    recent = c.career[:3] if c.career else []
    recent_families: list[str] = []
    recent_scores: list[float] = []
    for r in recent:
        fam, sc = _match_role(r.title)
        recent_families.append(fam)
        recent_scores.append(sc)

    avg_recent_score = sum(recent_scores) / len(recent_scores) if recent_scores else current_score

    # Tenure-only-at-consulting-firms check.
    companies = [normalise(r.company) for r in c.career] + [normalise(c.current_company)]
    companies = [x for x in companies if x]
    only_consulting = bool(companies) and all(
        any(firm in co for firm in CONSULTING_FIRMS) for co in companies
    )
    has_product_company = any(
        any(p in co for p in PRODUCT_COMPANY_HINTS) for co in companies
    )

    # JD: penalise people who haven't shipped code in last 18 months
    # (moved into pure "tech lead" / "architecture"). We approximate that by
    # current_title being a pure-management title.
    mgmt_titles = {"manager", "director", "head", "vp", "vice president", "chief"}
    cur_t = normalise(c.current_title)
    pure_mgmt = any(m in cur_t for m in mgmt_titles) and not any(
        eng in cur_t for eng in ("engineer", "developer", "scientist", "architect")
    )

    return {
        "current_family": current_family,
        "current_family_score": current_score,
        "avg_recent_family_score": avg_recent_score,
        "only_consulting": only_consulting,
        "has_product_company": has_product_company,
        "pure_management_track": pure_mgmt,
    }
