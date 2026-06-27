# Talentry AI — Intelligent Candidate Discovery & Ranking Engine

[![CI](https://github.com/williyam-m/talentry-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/williyam-m/talentry-ai/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-black.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-black.svg)](LICENSE)
[![HF Space](https://img.shields.io/badge/🤗%20Hugging%20Face-Space-black)](https://huggingface.co/spaces/williyam/talentry-ai)

> Submission to the **Redrob × Hack2Skill — India Runs**
> *Intelligent Candidate Discovery & Ranking Challenge*.

Talentry AI is an **AI brain for modern hiring** — a production-grade ranking
engine that moves beyond keyword filters to deeply understand context, predict
relevance, and turn a 100K candidate ocean into a precise, defensible top‑100
shortlist for a single job description.

The system is built for the constraints that actually matter in production:

| Constraint                       | Talentry AI                        |
| -------------------------------- | ---------------------------------- |
| Runtime (100K candidates)        | **≈ 90 seconds** on a CPU laptop   |
| Memory                           | **< 4 GB RAM**                     |
| GPU                              | **Not required**                   |
| Network during ranking           | **Zero** (no LLM API calls)        |
| Reproducibility                  | One command — `make submission`    |

---

## ✨ Why Talentry AI is different

Most "AI recruiters" reduce to a BM25 keyword filter with a fancy logo. They
get fooled by the **four traps** the Redrob organisers explicitly built into
this dataset:

1. **Keyword stuffers** — Marketing Managers who list `LangChain`,
   `Pinecone`, `Fine-tuning LLMs` as skills.
2. **Plain-language Tier‑5s** — real senior ML engineers who never use the
   word "RAG" but describe building production retrieval systems in prose.
3. **Behavioural twins** — paper-perfect candidates who haven't logged in for
   6 months.
4. **Honeypots** — ~80 subtly impossible profiles (8 yrs at a 3‑year-old
   company, *expert* skill with 0 months usage).

Talentry AI is engineered around these failure modes:

```
    Job Description
          │
          ▼
 ┌──────────────────────┐
 │  JD Understanding    │   Distilled requirements graph
 │  (LLM-free, rule +   │   • role family + seniority band
 │   semantic parser)   │   • must-have / nice-to-have / disqualifier skills
 └──────────┬───────────┘   • location, notice, behavioural priors
            │
            ▼
 ┌──────────────────────┐
 │  Candidate Index     │   Built once, reused per JD
 │  • BM25 over text    │   • Hybrid lexical + dense semantic
 │  • MiniLM embeddings │   • Skill graph, normalised titles
 └──────────┬───────────┘
            │
            ▼
 ┌──────────────────────┐
 │  Multi-signal Scorer │   Six explainable components:
 │                      │     1. Title-career alignment  (anti-stuffer)
 │                      │     2. Semantic JD-summary fit (hybrid retrieval)
 │                      │     3. Skill evidence score    (endorsement trust)
 │                      │     4. Experience band match
 │                      │     5. Location & logistics
 │                      │     6. Behavioural availability multiplier
 └──────────┬───────────┘
            │
            ▼
 ┌──────────────────────┐
 │  Honeypot Guard      │   Hard down-rank on impossible profiles
 └──────────┬───────────┘
            │
            ▼
 ┌──────────────────────┐
 │  Reasoning Composer  │   Per-candidate 1–2 sentence justification
 │                      │   that cites real facts from the profile
 └──────────┬───────────┘
            │
            ▼
       top-100 CSV
```

Every score component is **explainable** — at Stage‑4 manual review every
reasoning string cites real, verifiable facts from the candidate's profile.

---

## 🚀 Quick start

```bash
# 1. Clone
git clone https://github.com/williyam-m/talentry-ai.git
cd talentry-ai

# 2. Create an environment
python3.10 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. Place the official candidates.jsonl in data/raw/
cp /path/to/candidates.jsonl data/raw/

# 4. Produce the submission (≤ 5 min on a CPU laptop)
make submission
# or, equivalently:
python -m talentry.cli.rank \
    --candidates data/raw/candidates.jsonl \
    --jd configs/job_description.txt \
    --out data/output/submission.csv
```

The validator ships in the official bundle:

```bash
python "[PUB] India_runs_data_and_ai_challenge/India_runs_data_and_ai_challenge/validate_submission.py" \
       data/output/submission.csv
# → Submission is valid.
```

---

## 🖥️ Live demo (HuggingFace Space)

A modern React (Vite + TypeScript + Tailwind) frontend backed by FastAPI is
deployed at:

**https://huggingface.co/spaces/williyam/talentry-ai**

It accepts a small candidate sample (≤ 100 candidates) via upload or a one-click
preloaded fixture and produces a ranked CSV plus a live, drill-down dashboard
that shows **why** each candidate landed at their rank.

### v1.1 — Production hardening & richer UX

The Space ships with several upgrades that take it from "demo" to
"world-class production":

* **Schema-first ingestion.** Every upload is validated against
  `candidate_schema.json` before a single token is scored. Mismatches
  surface as a **GitHub-style green/red diff** so you can see exactly which
  required field is missing or which enum value is wrong.
* **Drag-and-drop résumé parsing.** Upload one or many résumés
  (PDF / DOCX / TXT / MD) and the backend produces schema-conformant
  candidate records using deterministic rule-based parsers — zero LLM
  hallucinations. Each record is re-validated against the schema before
  being handed to the ranker.
* **"Feed sample candidates"** — a one-click button to explore the UI
  using the bundled 50-row fixture.
* **Immersive 3D scroll-storytelling guide** powered by React Three
  Fiber + Lenis smooth scrolling. As you scroll the geometry morphs to
  illustrate the five pipeline stages (ingest → validate → understand →
  signals → ship) with the tech used at each step labelled inline.
* **Production hardening.** GZip middleware (5× smaller breakdown JSON),
  10 MB upload caps, structured 413/415/422 error responses, LRU result
  cache keyed by upload SHA-1 (~10 ms cache hits), request-id propagation,
  `x-elapsed-ms` headers, and `asyncio.to_thread` offload for the
  CPU-bound ranking + résumé parsing work so the event loop never blocks.
* **Code-split bundle.** Three.js / R3F / framer-motion ship as separate
  chunks so the above-the-fold first paint stays small (~35 KB gz app code).

#### New endpoints

| Verb | Path                         | Purpose                                              |
| ---- | ---------------------------- | ---------------------------------------------------- |
| GET  | `/api/schema`                | Returns the bundled `candidate_schema.json`.         |
| GET  | `/api/sample`                | Returns up to 100 candidates from the fixture.       |
| GET  | `/api/sample/download`       | Streams the full fixture as a download.              |
| POST | `/api/validate`              | Validates an upload, returns report + diff.          |
| POST | `/api/parse-resumes`         | Multi-file résumé → schema-conformant candidates.    |
| POST | `/api/rank`                  | Schema-gated by default; pass `skip_validation=true` to bypass. |


---

## 🧪 Testing

```bash
pytest -q             # unit tests
make lint             # ruff + black --check
make smoke            # end-to-end on the 50-candidate fixture
```

---

## 📚 Documentation

| Doc                                    | Audience               |
| -------------------------------------- | ---------------------- |
| [`docs/architecture.md`](docs/architecture.md) | Engineers / reviewers  |
| [`docs/methodology.md`](docs/methodology.md)   | Stage-4 reviewers      |
| [`docs/api.md`](docs/api.md)                   | API consumers          |
| [`docs/ui.md`](docs/ui.md)                     | Frontend developers    |
| [`docs/user-guide.md`](docs/user-guide.md)     | End users / recruiters |

---

## 🤖 AI tools declaration

Per the hackathon spec we declare honestly: this codebase was developed by
**Williyam M** with **Claude** used as a pair-programmer for architecture
discussion, code review, and documentation polish. No candidate data was ever
sent to a hosted LLM. The ranking pipeline contains **zero** network calls.

---

## 📜 License

MIT — see [`LICENSE`](LICENSE).
