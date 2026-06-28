# Talentry AI

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-black.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-black.svg)](LICENSE)
[![HF Space](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Space-black)](https://williyam-talentry-ai.hf.space)

> ### 🚀 Live demo: **https://williyam-talentry-ai.hf.space**
> Drag-and-drop a `candidates.jsonl` + a JD (`.docx` / `.pdf` / `.txt` / `.md`)
> and get a ranked, explainable shortlist plus a downloadable `Ranked_shortlist.csv`
> / `.xlsx` in seconds.

> Submission to the **Redrob x Hack2Skill - India Runs** Intelligent Candidate
> Discovery & Ranking Challenge.


Talentry AI is a production-grade ranking engine that turns a 100K candidate
pool into a precise, defensible top-100 shortlist for a single job description.

## Production constraints

| Constraint                | Talentry AI            |
| ------------------------- | ---------------------- |
| Runtime (100K candidates) | **< 90 sec.** (1 CPU)  |
| Memory                    | **< 4 GB RAM**         |
| GPU                       | **Not required**       |
| Network during ranking    | **0 LLM calls**        |
| Reproducibility           | `make submission`      |

## Why it is different

Most "AI recruiters" reduce to a BM25 keyword filter. They fall for the four
traps the Redrob organisers built into the dataset:

1. **Keyword stuffers** - Marketing Managers listing `LangChain`, `Pinecone`,
   `Fine-tuning LLMs` as skills.
2. **Plain-language seniors** - real ML engineers who describe building
   production retrieval systems in prose without using the word "RAG".
3. **Behavioural twins** - paper-perfect candidates inactive for 6+ months.
4. **Honeypots** - ~80 subtly impossible profiles (8 yrs at a 3-year-old
   company, *expert* skill with 0 months usage).

Talentry AI is engineered around these failure modes:

```
    Job Description
          |
          v
 +----------------------+
 |  JD Understanding    |   Distilled requirements graph
 |  (LLM-free, rule +   |   * role family + seniority band
 |   semantic parser)   |   * must / nice / disqualifier skills
 +----------+-----------+   * location, notice, behavioural priors
            |
            v
 +----------------------+
 |  Candidate Index     |   Built once, reused per JD
 |  * BM25 over text    |   * Hybrid lexical + dense semantic
 |  * MiniLM embeddings |   * Skill graph, normalised titles
 +----------+-----------+
            |
            v
 +----------------------+
 |  Multi-signal Scorer |   Six explainable components:
 |                      |     1. Title-career alignment  (anti-stuffer)
 |                      |     2. Semantic JD-summary fit (hybrid retrieval)
 |                      |     3. Skill evidence score    (endorsement trust)
 |                      |     4. Experience band match
 |                      |     5. Location & logistics
 |                      |     6. Behavioural availability multiplier
 +----------+-----------+
            |
            v
 +----------------------+
 |  Honeypot Guard      |   Hard down-rank on impossible profiles
 +----------+-----------+
            |
            v
 +----------------------+
 |  Reasoning Composer  |   Per-candidate 1-2 sentence justification
 |                      |   citing real facts from the profile
 +----------+-----------+
            |
            v
       top-100 CSV
```

Every score component is auditable and cites real fields from the profile.

## Quick start

```bash
# 1. Clone
git clone https://github.com/williyam-m/talentry-ai.git
cd talentry-ai

# 2. Create an environment
python3.10 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. Place the official candidates.jsonl in data/raw/
cp /path/to/candidates.jsonl data/raw/

# 4. Produce the submission (< 5 min, CPU-only)
make submission
# or:
python -m talentry.cli.rank \
    --candidates data/raw/candidates.jsonl \
    --jd configs/job_description.txt \
    --out data/output/submission.csv
```

Validate the output with the official validator:

```bash
python validate_submission.py data/output/submission.csv
# -> Submission is valid.
```

## Live demo (HuggingFace Space)

React (Vite + TypeScript + Tailwind) frontend backed by FastAPI:

* **App URL:** https://williyam-talentry-ai.hf.space
* **Repo on HF:** https://huggingface.co/spaces/williyam/talentry-ai

It accepts a candidate sample (<= 100 candidates) via upload or a one-click
preloaded fixture and produces a `Ranked_shortlist.{csv,xlsx}` download plus
a live, drill-down dashboard that shows **why** each candidate landed at
their rank.


### v1.1 - Production hardening

* **Schema-first ingestion.** Every upload is validated against
  `candidate_schema.json` before a single token is scored. Mismatches surface
  as a **git diff style report** so you can see exactly which required field
  is missing or which enum value is wrong.
* **Drag-and-drop resume parsing.** Upload one or many resumes
  (PDF / DOCX / TXT / MD) and the backend produces schema-conformant
  candidate records using deterministic rule-based parsers (no LLM
  hallucinations). Each record is re-validated against the schema before
  being handed to the ranker.
* **"Feed sample candidates"** - a one-click button to explore the UI
  using the default 50-row fixture.
* **Immersive 3D scroll guide** powered by React Three Fiber + Lenis smooth
  scrolling. As you scroll, the geometry morphs to illustrate the five
  pipeline stages (ingest -> validate -> understand -> signals -> ship)
  with the tech used at each step labelled inline.
* **Production hardening.** GZip middleware (5x smaller breakdown JSON),
  600 MB upload cap (fits the full 480 MB candidates.jsonl), structured
  413/415/422 error responses, LRU result cache keyed by upload SHA-1
  (~10 ms cache hits), request-id propagation, `x-elapsed-ms` headers,
  and `asyncio.to_thread` offload for the CPU-bound ranking + resume
  parsing work so the event loop never blocks.
* **Code-split bundle.** Three.js / R3F / framer-motion ship as separate
  chunks so the above-the-fold first paint stays small (~35 KB gz app).

### Endpoints

| Verb | Path                   | Purpose                                          |
| ---- | ---------------------- | ------------------------------------------------ |
| GET  | `/api/health`          | Liveness + version + max upload cap.             |
| GET  | `/api/schema`          | Returns the default `candidate_schema.json`.     |
| GET  | `/api/sample`          | Returns up to 100 candidates from the fixture.   |
| GET  | `/api/sample/download` | Streams the full fixture as a download.          |
| POST | `/api/validate`        | Validates an upload, returns report + diff.      |
| POST | `/api/parse-resumes`   | Multi-file resume to schema-conformant records.  |
| POST | `/api/rank`            | Schema-gated; `skip_validation=true` to bypass.  |
| GET  | `/api/submission.csv`  | Streams the validator-clean CSV for a session.   |

## Testing

```bash
pytest -q             # unit tests
make lint             # ruff + black --check
make smoke            # end-to-end on the 50-candidate fixture
```

## Documentation

| Doc                                            | Audience               |
| ---------------------------------------------- | ---------------------- |
| [`docs/architecture.md`](docs/architecture.md) | Engineers / reviewers  |
| [`docs/methodology.md`](docs/methodology.md)   | Stage-4 reviewers      |
| [`docs/api.md`](docs/api.md)                   | API consumers          |
| [`docs/ui.md`](docs/ui.md)                     | Frontend developers    |
| [`docs/user-guide.md`](docs/user-guide.md)     | End users / recruiters |

## AI tools declaration

Per the hackathon spec we declare honestly: this codebase was developed by
**Williyam M** with **Claude** used as a pair-programmer for architecture
discussion, code review, and documentation polish. No candidate data was
ever sent to a hosted LLM. The ranking pipeline contains **zero** network calls.

## License

MIT - see [`LICENSE`](LICENSE).
