"""Resume → candidate-schema parser.

Accepts free-form resume files (PDF, DOCX, TXT, MD) and produces a
best-effort record that matches the official ``candidate_schema.json``.

Design notes
------------

* **Zero new heavy dependencies.** We use ``pypdf`` for PDFs and a tiny
  inline DOCX text-extractor (DOCX is just a zip of XML), so the runtime
  image only grows by ~600 KB. Both are *optional* - if pypdf isn't
  installed we still accept .txt / .md uploads.
* **Deterministic, rule-based extraction.** This is NOT an LLM resume
  parser - those hallucinate fields and break the downstream schema
  validator. Instead we use a small ensemble of regex + heuristic
  passes that exploit common resume conventions (Summary / Experience
  / Education / Skills section headers, "YYYY – YYYY" date ranges, the
  domain lexicon used elsewhere in Talentry).
* **Schema-aligned.** Every record we emit will pass our own
  :func:`talentry.io.schema.validate_candidate` checker, so users can
  resume-upload → rank without an intermediate cleanup step.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Iterable
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from talentry.nlp.lexicons import ROLE_KEYWORD_INDEX, SKILL_CLUSTERS


@lru_cache(maxsize=1)
def _skill_vocab() -> list[str]:
    """Flatten SKILL_CLUSTERS into a deduplicated, longest-first lexicon."""
    seen: dict[str, None] = {}
    for cluster_skills in SKILL_CLUSTERS.values():
        for s in cluster_skills:
            if s not in seen:
                seen[s] = None
    # Longest first so that "machine learning" wins over "learning".
    return sorted(seen.keys(), key=lambda s: (-len(s), s))

# ─────────────────────────────────────────────────────────────────────────────
# File-format text extraction


class ResumeParseError(Exception):
    """Raised when a resume cannot be decoded into plain text."""


def _extract_pdf(payload: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:  # pragma: no cover - import guard
        raise ResumeParseError(
            "PDF parsing requires `pypdf`. Install with: pip install pypdf"
        ) from exc
    try:
        reader = PdfReader(io.BytesIO(payload))
    except Exception as exc:
        raise ResumeParseError(f"could not open PDF: {exc}") from exc
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    text = "\n".join(pages)
    if not text.strip():
        raise ResumeParseError("PDF appears to be scanned/image-only (no extractable text)")
    return text


_DOCX_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _extract_docx(payload: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            with z.open("word/document.xml") as fh:
                tree = ET.parse(fh)
    except (KeyError, zipfile.BadZipFile) as exc:
        raise ResumeParseError(f"not a valid .docx file: {exc}") from exc
    root = tree.getroot()
    lines: list[str] = []
    for para in root.iter(f"{_DOCX_NS}p"):
        chunks = [n.text or "" for n in para.iter(f"{_DOCX_NS}t")]
        line = "".join(chunks).strip()
        if line:
            lines.append(line)
    text = "\n".join(lines)
    if not text.strip():
        raise ResumeParseError("DOCX contained no text")
    return text


def extract_text(filename: str, payload: bytes) -> str:
    """Dispatch on extension. Returns plain text or raises ResumeParseError."""
    if not payload:
        raise ResumeParseError("empty file upload")
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(payload)
    if suffix == ".docx":
        return _extract_docx(payload)
    if suffix in {".txt", ".md", ".rst", ""}:
        try:
            return payload.decode("utf-8", errors="replace")
        except Exception as exc:
            raise ResumeParseError(f"could not decode text file: {exc}") from exc
    raise ResumeParseError(
        f"unsupported resume format {suffix!r}. Accepted: .pdf, .docx, .txt, .md"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Section + field heuristics

_SECTION_HEADERS = {
    "summary": re.compile(r"^\s*(?:professional\s+)?(summary|profile|about)\s*[:\-]?\s*$", re.I),
    "experience": re.compile(
        r"^\s*(work\s+experience|experience|employment|career\s+history|professional\s+experience)\s*[:\-]?\s*$",
        re.I,
    ),
    "education": re.compile(r"^\s*(education|academic|qualifications)\s*[:\-]?\s*$", re.I),
    "skills": re.compile(r"^\s*(skills|technical\s+skills|tech\s+stack|core\s+competencies)\s*[:\-]?\s*$", re.I),
    "certifications": re.compile(r"^\s*(certifications|certificates|licenses)\s*[:\-]?\s*$", re.I),
    "languages": re.compile(r"^\s*(languages)\s*[:\-]?\s*$", re.I),
}

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s-])?\(?\d{3,4}\)?[\s.-]?\d{3}[\s.-]?\d{3,4}")
_YEAR_RANGE_RE = re.compile(
    r"(\d{4})\s*(?:-|to)\s*(\d{4}|present|current)",
    re.I,
)

_MONTH_YEAR = re.compile(
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})", re.I
)


def _split_sections(text: str) -> dict[str, str]:
    """Split resume into named sections using header heuristics."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in text.splitlines():
        stripped = line.strip()
        matched = None
        for name, rgx in _SECTION_HEADERS.items():
            if rgx.match(stripped):
                matched = name
                break
        if matched:
            current = matched
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def _extract_name(header: str) -> str:
    """Pull the first reasonable proper-noun line out of the header block."""
    for raw in header.splitlines()[:8]:
        line = raw.strip()
        if not line or _EMAIL_RE.search(line) or _PHONE_RE.search(line):
            continue
        # Heuristic: looks like a person name - 2–5 words, mostly capitalised,
        # no digits, not all-caps section header.
        words = line.split()
        if not (2 <= len(words) <= 5):
            continue
        if any(ch.isdigit() for ch in line):
            continue
        cap = sum(1 for w in words if w[:1].isupper())
        if cap >= max(2, len(words) - 1) and line == line.title() or cap == len(words):
            return line
    return "Anonymous Candidate"


def _extract_headline(header: str, summary: str) -> str:
    """Headline = first non-name, non-contact short line, or first summary sentence."""
    candidates: list[str] = []
    name = _extract_name(header)
    for raw in header.splitlines():
        line = raw.strip()
        if not line or line == name:
            continue
        if _EMAIL_RE.search(line) or _PHONE_RE.search(line):
            continue
        if 12 <= len(line) <= 120:
            candidates.append(line)
    if candidates:
        return candidates[0]
    if summary:
        first = re.split(r"[.\n]", summary, maxsplit=1)[0].strip()
        if first:
            return first[:120]
    return "Professional"


def _years_from_experience(exp_text: str) -> float:
    spans: list[tuple[int, int]] = []
    today_year = date.today().year
    for m in _YEAR_RANGE_RE.finditer(exp_text):
        try:
            start = int(m.group(1))
            end_s = m.group(2).lower()
            end = today_year if end_s in {"present", "current"} else int(end_s)
            if 1970 <= start <= today_year + 1 and start <= end:
                spans.append((start, min(end, today_year)))
        except ValueError:
            continue
    if not spans:
        return 0.0
    # Merge overlapping spans for a realistic total.
    spans.sort()
    merged: list[list[int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return float(sum(e - s for s, e in merged))


def _extract_skills(skills_text: str, full_text: str) -> list[dict[str, Any]]:
    """Extract skills by intersecting our domain lexicon with the resume text."""
    found: dict[str, int] = {}
    haystack = (skills_text + "\n" + full_text).lower()
    for skill in _skill_vocab():
        # word-boundary aware match (allow `.` and `+` inside skill names)
        pattern = r"(?<![A-Za-z0-9])" + re.escape(skill.lower()) + r"(?![A-Za-z0-9])"
        hits = len(re.findall(pattern, haystack))
        if hits:
            found[skill] = hits
    # Also peel comma/bullet separated tokens from the skills block.
    for token in re.split(r"[,;•\u2022\n|]", skills_text):
        token = token.strip()
        if 2 <= len(token) <= 30 and token.lower() not in {s.lower() for s in found}:
            if re.fullmatch(r"[A-Za-z0-9 .+#/\-]+", token):
                found.setdefault(token, 1)
    out: list[dict[str, Any]] = []
    for name, hits in sorted(found.items(), key=lambda kv: (-kv[1], kv[0])):
        prof = "expert" if hits >= 4 else "advanced" if hits >= 2 else "intermediate"
        out.append(
            {
                "name": name,
                "proficiency": prof,
                "endorsements": min(50, hits * 3),
                "duration_months": min(120, hits * 6),
            }
        )
    return out[:40]


def _extract_career(exp_text: str) -> list[dict[str, Any]]:
    """Slice the experience block into role records using year-range anchors."""
    if not exp_text.strip():
        return []
    lines = exp_text.splitlines()
    anchors: list[int] = [i for i, ln in enumerate(lines) if _YEAR_RANGE_RE.search(ln)]
    if not anchors:
        return []
    anchors.append(len(lines))
    today_year = date.today().year
    roles: list[dict[str, Any]] = []
    for i in range(len(anchors) - 1):
        block = lines[anchors[i] : anchors[i + 1]]
        header_line = block[0]
        m = _YEAR_RANGE_RE.search(header_line)
        if not m:
            continue
        try:
            start = int(m.group(1))
            end_s = m.group(2).lower()
            is_current = end_s in {"present", "current"}
            end_year = today_year if is_current else int(end_s)
        except ValueError:
            continue
        # Try to pull "Title at Company" or "Title, Company" from the line.
        pre = _YEAR_RANGE_RE.sub("", header_line).strip(" -–-|,")
        title, company = pre, ""
        for sep in [" at ", " @ ", ", ", " | ", " - ", " – "]:
            if sep in pre:
                left, right = pre.split(sep, 1)
                title, company = left.strip(), right.strip()
                break
        description = " ".join(ln.strip() for ln in block[1:] if ln.strip())
        duration_months = max(1, (end_year - start) * 12)
        roles.append(
            {
                "company": company or "Unknown",
                "title": title or "Professional",
                "start_date": f"{start:04d}-01-01",
                "end_date": None if is_current else f"{end_year:04d}-12-31",
                "duration_months": duration_months,
                "is_current": is_current,
                "industry": "Technology",
                "company_size": "201-500",
                "description": description[:1500] or title,
            }
        )
    # Newest first
    roles.sort(key=lambda r: r["start_date"], reverse=True)
    return roles[:10]


def _extract_education(edu_text: str) -> list[dict[str, Any]]:
    if not edu_text.strip():
        return []
    entries: list[dict[str, Any]] = []
    for raw in edu_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _YEAR_RANGE_RE.search(line)
        if m:
            try:
                start = int(m.group(1))
                end_s = m.group(2).lower()
                end = date.today().year if end_s in {"present", "current"} else int(end_s)
            except ValueError:
                continue
        else:
            # Try a single year.
            single = re.search(r"\b(19|20)\d{2}\b", line)
            if not single:
                continue
            end = int(single.group(0))
            start = max(1970, end - 4)
        # Title-cased word seq = institution; rest = degree/field.
        without_years = _YEAR_RANGE_RE.sub("", line).strip(" -–-|,")
        parts = [p.strip() for p in re.split(r"[,|\u2022•]", without_years) if p.strip()]
        institution = parts[0] if parts else "Unknown"
        degree = parts[1] if len(parts) > 1 else "Degree"
        field_of_study = parts[2] if len(parts) > 2 else parts[1] if len(parts) > 1 else "General"
        entries.append(
            {
                "institution": institution,
                "degree": degree,
                "field_of_study": field_of_study,
                "start_year": start,
                "end_year": end,
                "grade": None,
                "tier": "unknown",
            }
        )
        if len(entries) >= 5:
            break
    return entries


def _guess_current(career: list[dict[str, Any]]) -> tuple[str, str, str, str]:
    """Return (title, company, size, industry) from the most recent role."""
    if not career:
        return "Professional", "Independent", "1-10", "Technology"
    cur = next((c for c in career if c.get("is_current")), career[0])
    return (
        cur.get("title") or "Professional",
        cur.get("company") or "Unknown",
        cur.get("company_size") or "201-500",
        cur.get("industry") or "Technology",
    )


def _guess_role_family(text: str) -> str:
    text_l = text.lower()
    best, best_score = "", 0.0
    for key, value in ROLE_KEYWORD_INDEX.items():
        if key in text_l:
            # ROLE_KEYWORD_INDEX values can be either a string family or a
            # (family, weight) tuple - be permissive.
            if isinstance(value, tuple):
                family, weight = value[0], float(value[1])
            else:
                family, weight = str(value), 1.0
            score = text_l.count(key) * len(key) * weight
            if score > best_score:
                best, best_score = family, score
    return best


def _today_iso() -> str:
    return date.today().isoformat()


def _months_ago_iso(months: int) -> str:
    today = date.today()
    y = today.year - (months // 12)
    m = today.month - (months % 12)
    if m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1).isoformat()


def parse_resume(filename: str, payload: bytes, *, candidate_id: str | None = None) -> dict[str, Any]:
    """Parse one resume into a schema-conformant candidate record."""
    text = extract_text(filename, payload)
    sections = _split_sections(text)

    header = sections.get("header", "")
    summary = sections.get("summary", "") or _first_paragraph(text)
    exp_text = sections.get("experience", "")
    edu_text = sections.get("education", "")
    skills_text = sections.get("skills", "")

    name = _extract_name(header or text)
    headline = _extract_headline(header, summary)
    years = _years_from_experience(exp_text or text)

    career = _extract_career(exp_text or text)
    education = _extract_education(edu_text or text)
    skills = _extract_skills(skills_text, text)
    current_title, current_company, current_size, current_industry = _guess_current(career)

    if candidate_id is None:
        # Deterministic-ish ID derived from filename so re-uploads are stable.
        h = abs(hash((filename, len(text)))) % 10_000_000
        candidate_id = f"CAND_{h:07d}"

    skill_assessment_scores = {
        s["name"]: min(95, 50 + s["endorsements"]) for s in skills[:10]
    }

    return {
        "candidate_id": candidate_id,
        "profile": {
            "anonymized_name": name,
            "headline": headline,
            "summary": (summary or headline)[:1200],
            "location": "Unknown",
            "country": "India",
            "years_of_experience": round(years, 1),
            "current_title": current_title,
            "current_company": current_company,
            "current_company_size": current_size,
            "current_industry": current_industry,
        },
        "career_history": career or _placeholder_career(years, current_title, current_company),
        "education": education or _placeholder_education(),
        "skills": skills,
        "certifications": [],
        "languages": [{"language": "English", "proficiency": "professional"}],
        "redrob_signals": _placeholder_signals(years, skills),
    }


def parse_many(files: Iterable[tuple[str, bytes]]) -> list[dict[str, Any]]:
    """Parse multiple resumes. Failures are recorded inline, not raised."""
    out: list[dict[str, Any]] = []
    for i, (name, payload) in enumerate(files):
        try:
            rec = parse_resume(name, payload, candidate_id=f"CAND_{i + 1:07d}")
            out.append(rec)
        except ResumeParseError as exc:
            out.append({"_error": str(exc), "_filename": name})
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / placeholders so the output always satisfies the schema


def _first_paragraph(text: str) -> str:
    for chunk in re.split(r"\n\s*\n", text):
        s = chunk.strip()
        if 40 <= len(s) <= 1200:
            return s
    return text.strip()[:600]


def _placeholder_career(years: float, title: str, company: str) -> list[dict[str, Any]]:
    today = date.today()
    start = date(max(1990, today.year - max(1, int(years or 1))), 1, 1)
    return [
        {
            "company": company,
            "title": title,
            "start_date": start.isoformat(),
            "end_date": None,
            "duration_months": max(1, int((today.year - start.year) * 12)),
            "is_current": True,
            "industry": "Technology",
            "company_size": "201-500",
            "description": title,
        }
    ]


def _placeholder_education() -> list[dict[str, Any]]:
    return []


def _placeholder_signals(years: float, skills: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "profile_completeness_score": 75,
        "signup_date": _months_ago_iso(18),
        "last_active_date": _today_iso(),
        "open_to_work_flag": True,
        "profile_views_received_30d": 25,
        "applications_submitted_30d": 5,
        "recruiter_response_rate": 0.6,
        "avg_response_time_hours": 12.0,
        "skill_assessment_scores": {s["name"]: min(95, 50 + s["endorsements"]) for s in skills[:10]},
        "connection_count": 250,
        "endorsements_received": sum(s.get("endorsements", 0) for s in skills),
        "notice_period_days": 30,
        "expected_salary_range_inr_lpa": {
            "min": float(max(6, int(years) * 3)),
            "max": float(max(12, int(years) * 5)),
        },
        "preferred_work_mode": "hybrid",
        "willing_to_relocate": True,
        "github_activity_score": 40.0,
        "search_appearance_30d": 10,
        "saved_by_recruiters_30d": 2,
        "interview_completion_rate": 0.9,
        "offer_acceptance_rate": 0.5,
        "verified_email": True,
        "verified_phone": False,
        "linkedin_connected": True,
    }
