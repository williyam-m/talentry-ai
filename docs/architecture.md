# Talentry AI - System Architecture

This document is the **engineer's guide** to Talentry AI. If you are reviewing
the codebase at Stage 3 (reproduction) or Stage 5 (defend-your-work) of the
Redrob × Hack2Skill - India Runs challenge, start here.

---

## 1. Goals and constraints

The challenge ([`submission_spec.md` §3](../configs/submission_spec.txt))
imposes a hard envelope on the ranking step:

| Constraint                  | Limit                       |
| --------------------------- | --------------------------- |
| Wall-clock runtime          | **≤ 5 minutes**             |
| RAM                         | **≤ 16 GB**                 |
| Compute                     | **CPU only**                |
| Network                     | **Off** (no LLM API calls)  |
| Disk (intermediate state)   | **≤ 5 GB**                  |

We additionally treat these *product* requirements as first-class:

* **Explainability** - every score must be defensible at Stage 4 manual review.
* **Reproducibility** - bit-for-bit reproducibility in a sandboxed Docker.
* **Anti-trap robustness** - the dataset deliberately contains keyword
  stuffers, plain-language Tier-5s, behavioural twins, and ~80 honeypots.
* **No hallucination in reasoning** - every reasoning string must reference
  only facts present in the candidate's own profile.

---

## 2. High-level architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              Talentry AI                                 │
│                                                                          │
│   ┌──────────┐    ┌──────────────┐    ┌────────────────────────────┐    │
│   │ JD text  │───▶│ JD Parser    │───▶│     JobRequirements         │    │
│   └──────────┘    │ (rules+lex)  │    │  • role family, seniority   │    │
│                   └──────────────┘    │  • must / nice / disqual.   │    │
│                                       │  • locations, behaviour      │    │
│                                       └──────────────┬─────────────┘    │
│                                                      │                  │
│                                                      ▼                  │
│   ┌──────────────────┐   ┌──────────────────┐   ┌─────────────────┐    │
│   │ candidates.jsonl │──▶│ Loader + models │──▶│ Feature builder │    │
│   └──────────────────┘   └──────────────────┘   │ (text_blob,     │    │
│                                                 │  role signals)  │    │
│                                                 └────────┬────────┘    │
│                                                          │             │
│            ┌─────────────────────────────────────────────┴───────┐     │
│            ▼                                                     ▼     │
│  ┌─────────────────┐                              ┌────────────────────┐│
│  │ BM25 + TF-IDF   │  hybrid semantic score      │ Skill Evidence     ││
│  │ hybrid index    │─────────────────┐           │ (cluster, stuffer  ││
│  └─────────────────┘                  │           │  detection)        ││
│                                       ▼           └────────┬───────────┘│
│                          ┌────────────────────────┐        │            │
│                          │   Scorer (5 weighted)  │◀───────┘            │
│                          │   + Behavioural × mul. │                      │
│                          │   − Honeypot penalty   │                      │
│                          └──────────┬─────────────┘                      │
│                                     ▼                                    │
│                          ┌────────────────────────┐                      │
│                          │ Sort + Reasoning + CSV │                      │
│                          └──────────┬─────────────┘                      │
│                                     ▼                                    │
│                                submission.csv                            │
└──────────────────────────────────────────────────────────────────────────┘
```

### Module → file mapping

| Module                       | File                                                       |
| ---------------------------- | ---------------------------------------------------------- |
| Domain models                | `src/talentry/core/models.py`                              |
| Tokeniser + synonyms         | `src/talentry/nlp/tokenize.py`                             |
| Domain lexicons              | `src/talentry/nlp/lexicons.py`                             |
| Candidate I/O                | `src/talentry/io/candidates.py`                            |
| Submission CSV writer        | `src/talentry/io/submission.py`                            |
| Per-candidate features       | `src/talentry/features/builder.py`                         |
| Skill evidence scoring       | `src/talentry/features/skill_match.py`                     |
| Behavioural multiplier       | `src/talentry/signals/behavioural.py`                      |
| Honeypot penalty             | `src/talentry/signals/honeypot.py`                         |
| Hybrid BM25+TF-IDF index     | `src/talentry/ranker/semantic.py`                          |
| JD parser                    | `src/talentry/ranker/jd_parser.py`                         |
| Scoring formulae             | `src/talentry/ranker/scorer.py`                            |
| Reasoning composer           | `src/talentry/ranker/reasoning.py`                         |
| End-to-end pipeline          | `src/talentry/ranker/engine.py`                            |
| CLI                          | `src/talentry/cli/rank.py`                                 |
| HTTP API (FastAPI)           | `src/talentry/api/server.py`                               |
| React UI                     | `ui/talentry-space/`                                       |

---

## 3. Why not dense embeddings?

Reviewers will rightly ask: "this is a retrieval challenge - why not a
sentence-transformer?" Three reasons:

1. **Budget.** Loading a 90 MB MiniLM and encoding 100K text blobs is right at
   the edge of the 5-minute CPU budget; once you add the per-row scoring,
   feature building, sort, and CSV write, you have no headroom for slow
   I/O on the Stage 3 sandbox.
2. **Dependency surface.** A serialised PyTorch model artifact is one more
   thing that can break reproduction; pure BM25 + TF-IDF reproduces from
   `pip install`-able libraries alone.
3. **Signal saturation.** BM25 saturates on rare-term overlap and TF-IDF
   smooths over phrasing - and that is exactly what this dataset rewards.
   Adding a dense model marginally improves recall on prose-only profiles
   but adds noise on the keyword surface where stuffers live.

If we had two hours and a GPU per ranking call we would absolutely add a
domain-fine-tuned reranker on the top 1000. We do not.

---

## 4. Composition formula

```
linear = 0.32·title_alignment
       + 0.22·semantic_fit
       + 0.28·skill_evidence
       + 0.12·experience_band
       + 0.06·location

final  = linear × behavioural_multiplier      ∈ [0.55, 1.20]
       − honeypot_penalty                     ∈ [0, 0.50]
       (clipped to [-0.5, 1.5])
```

Every constant is grounded in a specific line of the JD; see
[`methodology.md`](methodology.md) for the rationale.

---

## 5. Determinism

* Hot path uses no random state.
* `reference_date` for behavioural recency is overridable for tests.
* Sort tie-break: `candidate_id` ascending - matches the validator.
* CSV writer enforces the exact validator invariants at write-time so any
  drift fails loudly in the CLI, never silently at upload.

---

## 6. Threat model - the four traps

| Trap                  | Defence                                                        |
| --------------------- | -------------------------------------------------------------- |
| Keyword stuffer       | Skill *evidence* (endorsements × duration × proficiency)       |
| Plain-language Tier 5 | BM25 over career-description text + role-family trajectory     |
| Behavioural twin      | Behavioural multiplier in [0.55, 1.20]                         |
| Honeypot              | Honeypot penalty subtracts up to 0.50                          |

---

## 7. Operational notes

* CLI: `python -m talentry.cli.rank ...` (see `make submission`).
* API: `talentry-serve` (or `make serve`) → `http://localhost:7860`.
* UI: `make ui-dev` (`http://localhost:5173` with `/api` proxied).
* Container: `make docker-build && make docker-run` - same image is pushed to
  the HuggingFace Space.
