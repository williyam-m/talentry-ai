"""
Dataset builder for the Redrob candidate-ranking RL task.

We re-use the production Talentry-AI ranker (BM25 + TF-IDF + behavioural
signals + honeypot guard) to produce *gold* labels for every candidate, then
turn each (job-description, candidate) pair into a chat-style prompt that the
GRPO trainer can roll completions on.

Gold labelling rule
-------------------
1. Run ``talentry.ranker.rank_candidates`` over the candidate pool.
2. Anyone in the top-K is labelled ``"shortlist"`` with their final score as
   the gold scalar reward.
3. Everyone else is labelled ``"reject"`` and is paired with a gold scalar
   reward of ``1 - score`` (so a near-miss still carries useful signal).

The prompts include only fields the policy should be able to look at:
candidate headline, summary, current title/company, top skills, and the JD
summary. No leakage of the gold label.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence


# --------------------------------------------------------------------------- #
# Prompt template
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = (
    "You are RedRob, an explainable candidate-ranking assistant. "
    "Given a job description (JD) and a candidate profile you must decide "
    "whether the candidate should be SHORTLISTED for this role. "
    "Respond with a single JSON object and nothing else, of the form:\n"
    '{"decision": "shortlist" | "reject", "score": <float 0..1>, '
    '"reasons": ["short bullet 1", "short bullet 2", ...]}\n'
    "Rules:\n"
    "- 'score' is your confidence that the candidate fits the JD.\n"
    "- Provide 2-4 short, grounded reasons that cite the profile.\n"
    "- Do not invent skills or companies that are not in the profile.\n"
    "- Be strict on honeypots (impossible tenure, expert skill with 0 months)."
)


# --------------------------------------------------------------------------- #
# Public types
# --------------------------------------------------------------------------- #

@dataclass
class PromptSample:
    """A single training sample for GRPO."""

    prompt: str                # chat-templated prompt (string)
    context: str               # raw JD+candidate text for hallucination check
    decision: str              # "shortlist" | "reject"
    score: float               # gold scalar in [0, 1]
    candidate_id: str
    meta: Dict[str, str] = field(default_factory=dict)

    def to_record(self) -> Dict[str, object]:
        return {
            "prompt": self.prompt,
            "context": self.context,
            "decision": self.decision,
            "score": float(self.score),
            "candidate_id": self.candidate_id,
            **self.meta,
        }


# --------------------------------------------------------------------------- #
# Builder
# --------------------------------------------------------------------------- #

@dataclass
class DatasetBuilder:
    """
    Build prompt samples from a Redrob ``candidates.jsonl`` (or the bundled
    50-candidate fixture) and a job description text file.
    """

    candidates_path: Path
    jd_path: Path
    top_k: int = 20
    max_samples: int = 200
    seed: int = 7
    balance_classes: bool = True

    # ----- public ---------------------------------------------------------- #

    def build(self) -> List[PromptSample]:
        cands = self._load_candidates()
        jd_text = self._load_jd()
        ranked = self._rank(cands, jd_text)

        # gold labels
        top_ids = {r.candidate_id for r in ranked[: self.top_k]}
        score_by_id = {r.candidate_id: float(r.score) for r in ranked}

        samples: List[PromptSample] = []
        for c in cands:
            cid = self._cand_id(c)
            in_top = cid in top_ids
            decision = "shortlist" if in_top else "reject"
            base = score_by_id.get(cid, 0.0)
            gold = base if in_top else max(0.0, 1.0 - base)

            ctx = self._candidate_context(c)
            prompt = self._format_prompt(jd_text=jd_text, candidate_block=ctx)
            samples.append(
                PromptSample(
                    prompt=prompt,
                    context=f"{jd_text}\n\n{ctx}",
                    decision=decision,
                    score=round(float(gold), 4),
                    candidate_id=cid,
                    meta={"is_top": "1" if in_top else "0"},
                )
            )

        if self.balance_classes:
            samples = self._balance(samples)

        rng = random.Random(self.seed)
        rng.shuffle(samples)
        return samples[: self.max_samples]

    def write_jsonl(self, samples: Sequence[PromptSample], out_path: Path) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as fh:
            for s in samples:
                fh.write(json.dumps(s.to_record(), ensure_ascii=False) + "\n")
        return out_path

    # ----- private --------------------------------------------------------- #

    def _load_candidates(self) -> List[dict]:
        """Accepts both ``.json`` (list) and ``.jsonl`` (lines)."""
        p = Path(self.candidates_path)
        if not p.exists():
            raise FileNotFoundError(p)
        if p.suffix == ".jsonl":
            with p.open("r", encoding="utf-8") as fh:
                return [json.loads(line) for line in fh if line.strip()]
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "candidates" in data:
            return list(data["candidates"])
        raise ValueError(f"Unrecognised candidates file: {p}")

    def _load_jd(self) -> str:
        return Path(self.jd_path).read_text(encoding="utf-8").strip()

    @staticmethod
    def _cand_id(c: dict) -> str:
        return str(c.get("candidate_id") or c.get("id") or "")

    @staticmethod
    def _candidate_context(c: dict) -> str:
        prof = c.get("profile", {}) or {}
        skills = c.get("skills", []) or []
        career = c.get("career_history", []) or []
        top_skills = ", ".join(
            f"{s.get('name')} ({s.get('proficiency','?')}, "
            f"{int(s.get('duration_months',0))}m)"
            for s in skills[:8]
        )
        last = career[0] if career else {}
        bits = [
            f"Headline: {prof.get('headline','')}",
            f"Current: {prof.get('current_title','')} @ {prof.get('current_company','')} "
            f"({prof.get('current_company_size','?')})",
            f"YoE: {prof.get('years_of_experience','?')}",
            f"Location: {prof.get('location','')}, {prof.get('country','')}",
            f"Summary: {(prof.get('summary') or '')[:600]}",
            f"Top skills: {top_skills}",
            f"Latest role desc: {(last.get('description') or '')[:400]}",
        ]
        return "\n".join(bits)

    @staticmethod
    def _format_prompt(jd_text: str, candidate_block: str) -> str:
        return (
            f"[JOB DESCRIPTION]\n{jd_text[:1500]}\n\n"
            f"[CANDIDATE]\n{candidate_block}\n\n"
            "Decide whether to shortlist this candidate. "
            "Return only the JSON object specified by the system rules."
        )

    def _rank(self, cands: List[dict], jd_text: str):
        """
        Call the production ranker if available; otherwise fall back to a
        deterministic toy scorer so the notebook still runs in clean envs.
        """
        try:
            from talentry.core.models import Candidate
            from talentry.io.candidates import _candidate_from_dict  # type: ignore
            from talentry.ranker.engine import rank_candidates
            from talentry.ranker.jd_parser import parse_job_description

            jd = parse_job_description(jd_text)
            objs = []
            for raw in cands:
                try:
                    objs.append(_candidate_from_dict(raw))
                except Exception:
                    pass
            return rank_candidates(objs, jd, top_k=max(self.top_k * 4, 50))
        except Exception:
            return self._fallback_rank(cands, jd_text)

    @staticmethod
    def _fallback_rank(cands: List[dict], jd_text: str):
        """Very small bag-of-words overlap ranker for environments without
        the full Talentry package installed."""
        import re

        @dataclass
        class _R:
            candidate_id: str
            score: float

        jd_terms = set(re.findall(r"[a-zA-Z]{3,}", jd_text.lower()))
        out: List[_R] = []
        for c in cands:
            blob = json.dumps(c).lower()
            terms = set(re.findall(r"[a-zA-Z]{3,}", blob))
            overlap = len(jd_terms & terms) / max(len(jd_terms), 1)
            out.append(_R(str(c.get("candidate_id", "")), float(overlap)))
        out.sort(key=lambda r: -r.score)
        return out

    @staticmethod
    def _balance(samples: List[PromptSample]) -> List[PromptSample]:
        """Down-sample the majority class so positive == negative."""
        pos = [s for s in samples if s.decision == "shortlist"]
        neg = [s for s in samples if s.decision == "reject"]
        if not pos or not neg:
            return samples
        k = min(len(pos), len(neg))
        rng = random.Random(0)
        return rng.sample(pos, k) + rng.sample(neg, k)
