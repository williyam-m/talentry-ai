# Talentry AI - User Guide

Welcome. This guide is for **recruiters and HR teams** who want to use
Talentry AI to shortlist candidates.

---

## 1. What Talentry AI does

You give it:

* a pool of candidate profiles (JSON / JSONL), and
* a free-text job description.

It returns a **ranked top-100 shortlist** with a one-sentence justification
per candidate that quotes real facts from their profile.

It explicitly down-weights:

* keyword stuffers (people who list 10 AI skills but never used them);
* inactive candidates (no logins, low response rate);
* impossible profiles (the dataset's honeypots);
* career-misaligned profiles (e.g. Marketing Managers applying for an
  AI engineer role).

## 2. Trying it without installing anything

1. Open the live demo: **<https://huggingface.co/spaces/williyam/talentry-ai>**
   (Open-source fine-tuned LLM: <https://huggingface.co/williyam/redrob-qwen-grpo>)
2. Click **"Feed sample candidates"**.
3. You'll see the parsed JD card, a ranked-row table, and a per-candidate
   score breakdown with reasoning.

## 3. Running on your own data

1. Drop your `candidates.jsonl` (or `.json` / `.jsonl.gz`) onto the
   **Candidates** dropzone.
2. (Optional) Drop a custom job description: `.txt` / `.md` / `.docx` / `.pdf`.
   If left empty, the default Senior-AI-Engineer JD is used.
3. Set **Top-K = 100** if you want the validator-clean submission file.
4. Click **"Rank uploaded pool"**; download either `Ranked_shortlist.csv`
   (validator-clean) or `Ranked_shortlist.xlsx` (styled for human review).


## 4. Running locally (CLI)

```bash
git clone https://github.com/williyam-m/talentry-ai.git
cd talentry-ai
make venv install
cp /path/to/candidates.jsonl data/raw/
make submission
# → data/output/submission.csv
```

The validator from the official bundle should now report:

```
Submission is valid.
```

## 5. Interpreting the score breakdown

Every score has six visible components:

| Component               | What it captures                                              |
| ----------------------- | ------------------------------------------------------------- |
| Title alignment         | Did their actual career arc match the role?                   |
| Hybrid retrieval        | Does their profile text describe the work in the JD?           |
| Skill evidence          | Are their AI skills *backed* by endorsements / duration?      |
| Experience band         | Are they inside the years-of-experience window?               |
| Location                | Are they in Pune/Noida / Tier-1 India / willing to relocate?  |
| Behavioural multiplier  | Are they actually available (active / responsive / verified)? |

If the **final** score is mostly carried by `skill_evidence` but the
title alignment is near zero, you're looking at someone who knows the
tech stack but hasn't held the right kind of role - interview risk goes up.

## 6. Privacy and safety

* No candidate data ever leaves your machine.
* The ranking pipeline makes **zero** network calls.
* Reasoning strings are assembled from the candidate's own profile fields,
  so the system cannot hallucinate skills or employers.
