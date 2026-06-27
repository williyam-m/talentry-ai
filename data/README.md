# Redrob x Hack2Skill - India Runs : Talentry AI submission

This folder contains the **deliverable shortlist** for the
**Redrob x Hack2Skill - India Runs Data & AI Challenge**.

## Hackathon problem statement (verbatim)

> *Build an Intelligent Candidate Discovery & Ranking Engine.*
>
> Given a pool of **100,000 anonymised candidates** (`candidates.jsonl`,
> schema in `candidate_schema.json`) and a single Job Description for a
> Senior AI Engineer role at Redrob, produce a **ranked top 100** shortlist
> as a CSV / XLSX matching `sample_submission.csv` and conforming to the
> rules in `validate_submission.py`.
>
> Constraints:
> * **CPU only**, no GPU.
> * **No network / LLM calls** during ranking.
> * Reproducible: a single command must regenerate the submission.
> * Submission must pass the official `validate_submission.py` validator.
> * Evaluation is automated (LightGBM ground-truth match) **and** human
>   (manual reasoning review at Stage 4).

## What is in this folder

```
data/
├── README.md                # this file
├── raw/
│   ├── candidates.jsonl     # full 100,000-candidate pool (git-ignored)
│   └── sample_candidates.json   # 50-row fixture used by the HF Space
├── output/                  # local CLI smoke runs land here (git-ignored)
└── redrob_submission/
    ├── submission.csv       # *** OFFICIAL DELIVERABLE ***
    └── submission.xlsx      # same shortlist, styled for human review
```

## Inputs used to produce `redrob_submission/`

| Item                | Value                                                           |
| ------------------- | --------------------------------------------------------------- |
| Candidates file     | `data/raw/candidates.jsonl`                                     |
| Candidates count    | **100,000** records                                             |
| Job Description     | `India_runs_data_and_ai_challenge/job_description.docx`         |
| JD role / seniority | Senior AI Engineer (Founding Team), 5-9 yrs                     |
| Top-K               | 100                                                             |
| Engine version      | `talentry-ai v1.0.0` (commit `f4ea7a8`+)                        |

## Reproduce in one command

```bash
cd talentry-ai
source .venv/bin/activate            # or: pip install -e ".[dev]"

python -m talentry.cli.rank \
    --candidates data/raw/candidates.jsonl \
    --jd "/path/to/job_description.docx" \
    --out data/redrob_submission/submission.csv \
    --also-xlsx
```

Then validate against the official checker:

```bash
python "../[PUB] India_runs_data_and_ai_challenge/India_runs_data_and_ai_challenge/validate_submission.py" \
       data/redrob_submission/submission.csv
# -> Submission is valid.
```

## Output summary

* **`submission.csv`** - 1 header row + 100 ranked candidates,
  validator-clean (`candidate_id,rank,score,reasoning`).
* **`submission.xlsx`** - same shortlist materialised through `openpyxl`
  with frozen header row, sized columns and wrapped reasoning column.
  Both files have identical ranking and reasoning - use whichever your
  workflow prefers.

### Top 5 candidates produced for this JD

| rank | candidate_id    | score  | one-line summary                                                                          |
| ---: | :-------------- | -----: | :---------------------------------------------------------------------------------------- |
|    1 | `CAND_0086022`  | 1.0673 | Senior Applied Scientist, 5.3 yrs, Kolkata - retrieval/ranking work at Sarvam AI          |
|    2 | `CAND_0068351`  | 1.0476 | Lead AI Engineer, 6.4 yrs, Delhi - retrieval/ranking work at Sarvam AI                    |
|    3 | `CAND_0002025`  | 1.0272 | Senior AI Engineer, 5.9 yrs, Trivandrum - retrieval/ranking work at Apple                 |
|    4 | `CAND_0008425`  | 1.0240 | Senior NLP Engineer, 7.8 yrs, Kolkata - retrieval/ranking work at Ola                     |
|    5 | `CAND_0018499`  | 1.0181 | Senior ML Engineer, 7.2 yrs, Noida - retrieval/ranking work at Zomato                     |

Run the CLI again at any time to refresh the table; the ranker is fully
deterministic given the same `candidates.jsonl` + JD pair.

## How the engine ranks (summary)

1. **Stream-ingest** the 100K JSONL pool through a slotted-dataclass loader.
2. **Schema-validate** every record against `candidate_schema.json` (failures
   surface as a git-diff-style report in the UI).
3. **Parse the JD** into a `JobRequirements` DTO (role family, seniority
   band, must / nice / disqualifier skills).
4. **Score** every candidate on 6 explainable signals: title-career alignment
   (anti keyword-stuffer), hybrid BM25 + TF-IDF semantic JD fit,
   skill-evidence with endorsement trust, experience-band match, location
   & logistics, behavioural availability.
5. **Honeypot guard** down-ranks impossible profiles
   (e.g. 8 yrs at a 3-year-old company).
6. **Compose** a 1-2 sentence reasoning citing real facts from the profile.
7. **Write** the validator-clean CSV + XLSX.

Runtime on a single CPU for the full 100K pool: **~3 min 23 sec** wall-clock.

## License

MIT - see `../LICENSE`.
