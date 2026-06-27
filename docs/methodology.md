# Talentry AI - Methodology

This is the document a **Stage-4 reviewer** should read. Every modelling
decision is justified against a specific line of
[`configs/job_description.txt`](../configs/job_description.txt) or
[`configs/redrob_signals_doc.txt`](../configs/redrob_signals_doc.txt).

---

## 1. The mandate, reread

The JD explicitly closes with:

> The "right answer" to this JD is not "find candidates whose skills section
> contains the most AI keywords." That's a trap we've explicitly built into
> the dataset. … A candidate who has all the AI keywords listed as skills but
> whose title is 'Marketing Manager' is not a fit, no matter how perfect
> their skill list looks. … Your ranking system should also weigh behavioural
> signals - a perfect-on-paper candidate who hasn't logged in for 6 months
> and has a 5% recruiter response rate is, for hiring purposes, not actually
> available. Down-weight them appropriately.

Talentry AI's six scoring components map 1:1 onto these requirements.

---

## 2. The six components

### 2.1 Title alignment (weight 0.32)

A free-text title is mapped onto a **role family** via the lexicon in
`nlp/lexicons.py::ROLE_FAMILIES`. Scores range from `3.0` (ML / search-IR
engineer) down to `-1.0` (Marketing Manager, etc.).

Two trajectory amplifiers:

* `-0.40` if every employer on the candidate's CV is a consulting firm
  (JD: *"People who have only worked at consulting firms in their entire
  career"*).
* `-0.20` if the current title is a pure management track without "engineer
  / developer / scientist / architect" anywhere (JD: *"this role writes code"*).
* `+0.10` if there is at least one product-company employer (JD: *"applied
  ML at product companies (not pure services)"*).

### 2.2 Semantic fit (weight 0.22)

A hybrid retrieval score combining:

* **BM25** (60%) - rare-term overlap; e.g. "FAISS", "RAG", "NDCG".
* **TF-IDF cosine** (40%) - topical similarity that smooths over phrasing
  differences ("retrieval", "search", "ranking" should cluster together).

We min-max normalise each to [0,1] before combining so the two stay
comparable across query lengths.

Why no dense embeddings? See [`architecture.md` §3](architecture.md#3-why-not-dense-embeddings).

### 2.3 Skill evidence (weight 0.28) - the anti-stuffer core

Each claimed skill gets a **trust score** in [0, 1]:

```
trust = 0.40·proficiency + 0.20·endorsements + 0.10·duration + 0.30·assessment
        (where assessment is present;
         else 0.55·proficiency + 0.25·endorsements + 0.20·duration)
```

* Proficiency: `beginner=0.25 / intermediate=0.55 / advanced=0.85 / expert=1.0`
* Endorsements saturate at 50 (per dataset max ≈ 60).
* Duration saturates at 36 months.

Trust scores are then aggregated per **skill cluster** (six clusters -
`embeddings_retrieval`, `ranking_recsys`, `nlp_llm`, `ml_core`,
`python_engineering`, `data_engineering`) normalised to [0,1] by dividing by
`min(cluster_size, 4)`.

A stuffer signal - `keyword_stuff_ratio` - counts AI-keyword surface claims
that look padded (advanced/expert + ≤2 endorsements + ≤6 months + no
assessment, *or* trust < 0.40). When the ratio ≥ 0.7 the cluster sum is
discounted by 35%.

A CV/speech dominance signal - if ≥ 55% of total trust is in CV-only or
speech-only skills, the cluster sum is discounted by 45% (JD: *"primary
expertise is computer vision, speech, or robotics … you'd be re-learning
fundamentals here"*).

### 2.4 Experience band (weight 0.12)

Triangular score, `1.0` inside `[min_years, max_years]`, soft-decaying
outside. The JD: *"5-9 is a range, not a requirement … we'll seriously
consider candidates outside the band if other signals are strong"* - hence
the soft decay rather than a hard cutoff.

### 2.5 Location (weight 0.06)

Hierarchical preference:

| Location bucket                              | Score (willing/not) |
| -------------------------------------------- | ------------------- |
| Pune / Noida / Delhi NCR                     | 1.00                |
| Other Tier-1 India (Bangalore, Hyd, …)       | 0.85 / 0.75         |
| Other India                                  | 0.65 / 0.45         |
| Outside India                                | 0.30 / 0.10         |

### 2.6 Behavioural multiplier × Honeypot penalty

Multiplier components (sum + 1.0, clipped to [0.55, 1.20]):

| Component                | Contribution                                    |
| ------------------------ | ----------------------------------------------- |
| Activity recency         | +0.12 / +0.05 / -0.05 / -0.20 at 30/90/180/180+ |
| Recruiter response rate  | `(rr − 0.40) × 0.30`                            |
| Interview completion     | `(icr − 0.50) × 0.15`                           |
| Open-to-work flag        | +0.05 / -0.02                                   |
| Verifications            | +0.015 email, +0.015 phone, +0.02 linkedin      |
| Notice period            | +0.05 / 0 / -0.04 / -0.08 at ≤30/60/90/90+      |
| Saved by recruiters 30d  | up to +0.05                                     |

Honeypot penalty (subtracted, capped at 0.50):

* +0.18 if career-month sum exceeds declared years by ≥ 24 mo;
* +0.15 if ≥ 3 expert/advanced claims have zero endorsements **and** ≤ 2 mo
  of usage;
* +0.10 if multiple `is_current=True` roles;
* +0.08 if salary band is inverted (min > max);
* +0.04 if `signup_date` is after `last_active_date`;
* +0.03 if max education end-year is way after the candidate's current-role
  start year.

---

## 3. Reasoning composition (Stage-4 anti-hallucination)

`ranker/reasoning.py` builds every per-row sentence from facts already in
the candidate's profile. The structure is:

```
"<tone-phrase> - <role + years + location>; <strongest evidence>. Concerns: <…>."
```

The "strongest evidence" span is picked by preference order:

1. A career-history description that mentions
   retrieval / ranking / embedding / search / recommendation / RAG / vector
   / FAISS / Elasticsearch / LTR - *quoted with company name + tenure*.
2. The strongest skill cluster (only if ≥ 0.40 and not the AI-keyword surface).
3. A top assessed skill (proficiency + duration + assessment score).
4. Fallback: current title + employer.

Concerns are emitted *only when present* - long notice, low activity,
stuffer profile, CV/speech dominance, consulting-only career, or honeypot
suspicion. Each concern phrase quotes a real numeric fact (e.g.
`"long notice 120d"`).

This satisfies Stage 4's six checks (specific facts, JD connection, honest
concerns, no hallucination, variation, rank consistency) **by construction**.

---

## 4. Reproducibility checklist

* `pyproject.toml` pins minimum versions of every dependency.
* The pipeline is single-threaded and uses no random state.
* `reference_date` for behavioural recency is overridable.
* The CSV writer re-implements every `validate_submission.py` invariant and
  fails fast on violation.
* Smoke run reproduces the same ranking for the same input.
* `make docker-build && make docker-run` reproduces the full stack inside
  the same image we deploy to HuggingFace Spaces.
