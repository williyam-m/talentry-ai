# Talentry AI - HTTP API

The FastAPI server (`talentry-serve` or the bundled HuggingFace Space) exposes
three endpoints. All payloads are JSON; the only non-JSON response is the
CSV download.

Base URL inside the Space: `https://huggingface.co/spaces/williyam/talentry-ai`
(the same origin serves the React SPA).

---

## `GET /api/health`

Liveness probe.

```json
{ "status": "ok", "version": "1.0.0" }
```

---

## `GET /api/sample?limit=10`

Return up to `limit` candidate records from the bundled 50-row fixture
(`data/raw/sample_candidates.json`). Useful for UI bootstrapping.

`limit` is clamped to `[1, 100]`. Returns an array of raw candidate dicts
matching `candidate_schema.json`.

---

## `POST /api/rank?use_sample=false&top_k=10`

Run the full ranking pipeline.

**Multipart body:**

| Field        | Required             | Notes                                                |
| ------------ | -------------------- | ---------------------------------------------------- |
| `candidates` | yes unless `use_sample=true` | `.json` / `.jsonl` / `.jsonl.gz` upload     |
| `jd`         | no                   | `.txt` / `.md`; defaults to the bundled JD           |

**Query parameters:**

| Name         | Default | Notes                                                         |
| ------------ | ------- | ------------------------------------------------------------- |
| `use_sample` | `false` | If true, ignores `candidates` and uses the bundled fixture.   |
| `top_k`      | `10`    | Clamped to `[1, 100]`. Validator-clean CSV only at `top_k=100`. |

**Response:**

```jsonc
{
  "version": "1.0.0",
  "jd": {
    "title": "Senior AI Engineer",
    "seniority": "senior",
    "min_years": 5.0,
    "max_years": 9.0,
    "must_have_skills": [...],
    "preferred_locations": [...]
  },
  "n_candidates": 50,
  "n_returned": 10,
  "session_id": null,
  "results": [
    {
      "candidate_id": "CAND_0000031",
      "rank": 1,
      "score": 1.0101,
      "reasoning": "Strong match - Recommendation Systems Engineer ...",
      "breakdown": {
        "title_alignment": 0.9,
        "semantic_fit": 0.74,
        "skill_evidence": 0.81,
        "experience_band": 1.0,
        "location": 0.85,
        "behavioural": 1.18,
        "honeypot_penalty": 0.0,
        "final": 1.0101
      }
    }
  ]
}
```

When `top_k=100` *and* the input has ≥ 100 candidates, a `session_id` is
returned and the CSV is persisted for download.

---

## `GET /api/submission.csv?session=<id>`

Download the validator-clean 100-row CSV produced by a prior `/api/rank`
call that requested `top_k=100`.

Sessions are kept in process memory and will not survive a restart.

---

## CORS

The server allows all origins (`*`) so the UI and any external sandbox
checker can call it freely.
