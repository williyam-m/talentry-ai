"""Rule-based job-description parser.

We do *not* use an LLM here, for two reasons:

1. The hackathon explicitly disallows network calls during ranking and only
   ~5 minutes of CPU budget for 100K candidates. A local LLM is overkill
   for converting a single, long-but-well-structured JD into the
   :class:`JobRequirements` dataclass.
2. We have only one JD to handle in this challenge and we have read it
   carefully. A 200-line parser with documented assumptions is easier to
   audit at Stage 5 (the defend-your-work interview) than a few hundred
   LLM tokens.

The parser is tolerant: it reads any JD-like text but knows specifically how
to pull the right facts out of the Redrob Senior-AI-Engineer JD shipped with
the hackathon bundle.
"""

from __future__ import annotations

import re
from pathlib import Path

from talentry.core.models import JobRequirements
from talentry.nlp.lexicons import (
    CONSULTING_FIRMS,
    PREFERRED_LOCATIONS,
    TIER1_INDIA_LOCATIONS,
)

_YEARS_RE = re.compile(r"(\d+)\s*[-–to]+\s*(\d+)\s*year", re.I)
_NOTICE_RE = re.compile(r"(sub-?(\d+)|<\s*(\d+))\s*day", re.I)

# Skills the JD lists as "things you absolutely need".
_MUST_HAVE_SEED: list[str] = [
    "embeddings",
    "sentence transformers",
    "vector database",
    "FAISS",
    "Pinecone",
    "Weaviate",
    "Qdrant",
    "Milvus",
    "OpenSearch",
    "Elasticsearch",
    "BM25",
    "hybrid search",
    "information retrieval",
    "ranking",
    "NDCG",
    "MRR",
    "Python",
    "evaluation",
]

# Skills the JD lists as "nice to have".
_NICE_TO_HAVE_SEED: list[str] = [
    "LoRA",
    "QLoRA",
    "PEFT",
    "fine-tuning",
    "learning to rank",
    "XGBoost",
    "LightGBM",
    "distributed systems",
    "MLOps",
    "recsys",
]

# Title patterns the JD flat-out disqualifies (computer-vision-only, etc.).
_DISQUALIFIER_SEED: list[str] = [
    "computer vision only",
    "speech only",
    "robotics only",
]


def _read(jd: str | Path | None) -> str:
    """Read JD source. Accepts a Path / path-like / raw string.

    File formats supported: .txt, .md, .docx, .pdf. Anything else is read
    as UTF-8 text. A raw string that does not name an existing file is
    returned as-is (this is how the API passes already-extracted text in,
    e.g. after decoding a .docx upload).
    """
    if jd is None:
        return _DEFAULT_JD_TEXT
    if isinstance(jd, Path):
        return _read_path(jd)
    if isinstance(jd, str):
        # Only treat the string as a path if it's short enough to be one and
        # actually points at an existing file. Long blobs of JD prose blow
        # past the OS filename limit and would raise ENAMETOOLONG inside
        # Path(jd).exists() — that's how the server was returning HTTP 500
        # whenever an uploaded .docx was decoded to a multi-KB string.
        if len(jd) < 1024 and "\n" not in jd:
            try:
                p = Path(jd)
                if p.exists():
                    return _read_path(p)
            except OSError:
                pass
        return jd
    return str(jd)


def _read_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        from talentry.io.resume import _extract_docx
        return _extract_docx(path.read_bytes())
    if suffix == ".pdf":
        from talentry.io.resume import _extract_pdf
        return _extract_pdf(path.read_bytes())
    # Plain text — be permissive about encoding (the bundled JD ships
    # as UTF-8 but uploads may be cp1252 / latin-1).
    return path.read_text(encoding="utf-8", errors="replace")




def _extract_skills_from_section(text: str, section_markers: list[str], stop_markers: list[str]) -> list[str]:
    """Scan `text` for any of the seed skills appearing in the named section.

    Sections are matched case-insensitively. We take everything between the
    first ``section_marker`` line and the next ``stop_marker`` line (or EOF),
    then intersect with our domain skill vocabulary so we only return skills
    we know how to score downstream.
    """
    lower = text.lower()
    start = -1
    for marker in section_markers:
        idx = lower.find(marker.lower())
        if idx >= 0 and (start == -1 or idx < start):
            start = idx
    if start < 0:
        return []
    rest = lower[start:]
    end = len(rest)
    for marker in stop_markers:
        idx = rest.find(marker.lower(), 1)
        if 0 < idx < end:
            end = idx
    body = rest[:end]
    pool = set(_MUST_HAVE_SEED + _NICE_TO_HAVE_SEED + _DISQUALIFIER_SEED)
    found: list[str] = []
    for skill in sorted(pool, key=lambda s: (-len(s), s)):
        if skill.lower() in body and skill not in found:
            found.append(skill)
    return found


def parse_job_description(jd: str | Path | None = None) -> JobRequirements:
    """Parse a free-text JD into :class:`JobRequirements`.

    When called with ``None`` the bundled Senior-AI-Engineer JD text is used,
    so the API and CLI can be invoked without a JD file in trivial demos.

    Skill lists (must / nice / disqualifier) are extracted from the
    *uploaded* JD when possible — the hardcoded seeds are only the
    vocabulary we know how to score, not a fixed answer key.

    IMPORTANT: when the caller provides a non-empty ``jd`` (string, Path,
    or already-extracted text), we treat it as the authoritative source.
    The default Senior-AI-Engineer JD is only used when ``jd is None`` or
    when the supplied text is blank. This guarantees the API/UI cannot
    silently fall back to the bundled JD after a user uploaded their own.
    """
    # Was the JD supplied by the caller (uploaded) vs. defaulted?
    caller_supplied = jd is not None and (not isinstance(jd, str) or jd.strip() != "")
    text = _read(jd)
    if not text.strip():
        # Pathological case: the upload decoded to whitespace. Fall back
        # to the bundled JD rather than producing an empty parse.
        text = _DEFAULT_JD_TEXT
        caller_supplied = False
    lower = text.lower()


    # Years band
    match = _YEARS_RE.search(text)
    if match:
        min_y, max_y = float(match.group(1)), float(match.group(2))
    else:
        min_y, max_y = 5.0, 9.0

    # Title - first line that looks like a title.
    title = "Senior AI Engineer"
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("job description") and ":" in line:
            title = line.split(":", 1)[1].strip().split("-")[0].strip()
            break

    # Seniority bucket - we hard-bias to "senior" for this JD but parse the
    # word for future generality.
    if "principal" in lower or "staff" in lower:
        seniority = "staff+"
    elif "senior" in lower:
        seniority = "senior"
    elif "junior" in lower or "fresher" in lower:
        seniority = "junior"
    else:
        seniority = "mid"

    notice_match = _NOTICE_RE.search(text)
    pref_notice = int(notice_match.group(2) or notice_match.group(3)) if notice_match else 30

    # Skills: try to extract from the uploaded JD; fall back to seeds if
    # the JD doesn't use the expected section headers.
    must_have = _extract_skills_from_section(
        text,
        section_markers=["must have", "must-have", "requirements", "what you'll do", "qualifications", "you have"],
        stop_markers=["nice to have", "nice-to-have", "preferred", "bonus", "do not want", "we offer", "benefits"],
    ) or _MUST_HAVE_SEED
    nice_have = _extract_skills_from_section(
        text,
        section_markers=["nice to have", "nice-to-have", "preferred", "bonus", "good to have"],
        stop_markers=["do not want", "we offer", "benefits", "about us", "what we offer"],
    ) or _NICE_TO_HAVE_SEED
    disqualifiers = _extract_skills_from_section(
        text,
        section_markers=["do not want", "do not", "disqualif", "we will not"],
        stop_markers=["we offer", "benefits", "about us"],
    ) or _DISQUALIFIER_SEED

    return JobRequirements(
        title=title,
        role_family="ml_engineer",
        seniority=seniority,
        min_years=min_y,
        max_years=max_y,
        must_have_skills=must_have,
        nice_to_have_skills=nice_have,
        disqualifier_skills=disqualifiers,

        preferred_locations=sorted(PREFERRED_LOCATIONS),
        relocation_friendly_locations=sorted(TIER1_INDIA_LOCATIONS),
        preferred_notice_days=pref_notice,
        soft_notice_days=90,
        consulting_firms_penalised=sorted(CONSULTING_FIRMS),
        product_company_bonus=True,
        behavioural_priors={
            "min_response_rate": 0.3,
            "min_interview_completion": 0.4,
            "max_inactivity_days": 180,
        },
        raw_text=text,
    )


# A compact fallback so the package is usable even without the JD file.
_DEFAULT_JD_TEXT = """Job Description: Senior AI Engineer - Founding Team
Company: Redrob AI (Series A AI-native talent intelligence platform)
Location: Pune/Noida, India (Hybrid). Open to Tier-1 Indian cities.
Experience Required: 5–9 years.

Must have: production experience with embeddings-based retrieval
(sentence-transformers, BGE/E5/OpenAI embeddings), vector databases
(Pinecone/Weaviate/Qdrant/Milvus/OpenSearch/Elasticsearch/FAISS), hybrid
search, strong Python, hands-on evaluation frameworks (NDCG, MRR, MAP).

Nice to have: LoRA/QLoRA/PEFT fine-tuning, learning-to-rank, MLOps,
distributed systems, open-source contributions.

Do NOT want: marketing managers, sales execs, pure consulting-firm careers,
CV/speech/robotics-only specialists, candidates inactive on the platform.

Notice: sub-30-day preferred. 30+ day candidates considered but bar is higher.
"""
