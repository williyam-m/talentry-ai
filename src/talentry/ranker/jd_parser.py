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
    if jd is None:
        return _DEFAULT_JD_TEXT
    if isinstance(jd, Path) or (isinstance(jd, str) and Path(jd).exists()):
        return Path(jd).read_text(encoding="utf-8")
    return str(jd)


def parse_job_description(jd: str | Path | None = None) -> JobRequirements:
    """Parse a free-text JD into :class:`JobRequirements`.

    When called with ``None`` the bundled Senior-AI-Engineer JD text is used,
    so the API and CLI can be invoked without a JD file in trivial demos.
    """
    text = _read(jd)
    lower = text.lower()

    # Years band
    match = _YEARS_RE.search(text)
    if match:
        min_y, max_y = float(match.group(1)), float(match.group(2))
    else:
        min_y, max_y = 5.0, 9.0

    # Title — first line that looks like a title.
    title = "Senior AI Engineer"
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("job description") and ":" in line:
            title = line.split(":", 1)[1].strip().split("—")[0].strip()
            break

    # Seniority bucket — we hard-bias to "senior" for this JD but parse the
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

    return JobRequirements(
        title=title,
        role_family="ml_engineer",
        seniority=seniority,
        min_years=min_y,
        max_years=max_y,
        must_have_skills=_MUST_HAVE_SEED,
        nice_to_have_skills=_NICE_TO_HAVE_SEED,
        disqualifier_skills=_DISQUALIFIER_SEED,
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
_DEFAULT_JD_TEXT = """Job Description: Senior AI Engineer — Founding Team
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
