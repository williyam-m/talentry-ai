# Methodology — GRPO fine-tuning of Qwen3-0.6B on the Redrob task

## 1. Problem framing

The task is a **single-turn contextual bandit**:

* **State / observation** — a prompt containing a job description (JD) and one
  candidate profile.
* **Action** — a short JSON text completion of the form
  `{"decision": "shortlist"|"reject", "score": float, "reasons": [...]}`.
* **Reward** — scalar in `[0, 1]` produced by a deterministic, rule-based
  reward model (see §3).
* **Episode** — always exactly one step (`terminated = True`).

Framing the problem this way lets us reuse the Gymnasium API (one
`reset()` / `step()` per candidate) while still being a great fit for GRPO,
which evaluates groups of completions per prompt without needing a value
function or replay buffer.

## 2. Dataset construction

Inputs:

* `data/raw/sample_candidates.json` — the 50-candidate Redrob fixture.
* `configs/job_description.txt`     — the official JD.

Gold labels are produced by **Talentry-AI’s production ranker**
(`talentry.ranker.engine.rank_candidates`) — the deterministic BM25 + TF-IDF
+ behavioural-signals + honeypot-guard system. Candidates in the top-K are
labelled `"shortlist"` with their ranker score; the rest are labelled
`"reject"` with `1 - score` to keep useful gradient signal away from the
shortlist.

We then *balance* the two classes so the policy can't just learn the
majority label, shuffle with a fixed seed, and cap to `max_samples`
(default 64 for the local run).

This gives us a small but high-quality, hand-engineered dataset — perfect
for showing that even a 600M-param model can be nudged toward the correct
behaviour with only a few dozen optimiser steps.

## 3. Reward model — rule-based, six components

A learned reward model or LLM-as-a-judge would defeat the point of the
exercise (no LLM calls during training, reproducible). Instead, each
completion is scored on six dimensions, each clipped to `[0, 1]`:

1. `format_valid` — output parses as a JSON object with the required keys.
2. `decision_match` — `1` if predicted decision equals gold.
3. `score_alignment` — `1 - |pred_score - gold_score|`.
4. `reason_quality` — at least 2 short, diverse reasons that aren't
   copy-pasted from the input.
5. `length_penalty` — completion stays within a sensible character budget.
6. `no_hallucination` — every numeric token / proper noun in the reasons
   appears in the (JD + candidate) context.

The final reward is the convex combination using configurable weights:

```
total = (0.20 * format_valid
       + 0.30 * decision_match
       + 0.15 * score_alignment
       + 0.15 * reason_quality
       + 0.05 * length_penalty
       + 0.15 * no_hallucination)
```

(weights normalised so total ∈ `[0, 1]`).

## 4. Algorithm — GRPO

**Group Relative Policy Optimisation** (Shao et al., 2024 — the algorithm
behind DeepSeek-R1) is well-suited here:

* No value function needed.
* Works directly off scalar rewards from a custom function.
* Sample-efficient on small datasets with `num_generations` completions per
  prompt as the implicit baseline.

For each prompt we generate `num_generations = 4` completions, compute the
six-component reward for each, take the within-group advantage, and update
the policy with a clipped surrogate + KL term toward the *frozen* base
model.

We use the TRL implementation (`trl.GRPOTrainer`) for stability.

## 5. Training set-up

Hardware: **Apple M1 Pro, 16 GB**, Metal Performance Shaders (MPS).

Hyper-parameters (see `configs/grpo_qwen3_0p6b.yaml`):

| Parameter                    | Value     |
| ---------------------------- | --------- |
| Base model                   | `Qwen/Qwen3-0.6B` |
| `num_generations`            | 4         |
| `per_device_train_batch_size`| 1         |
| `gradient_accumulation_steps`| 4         |
| `learning_rate`              | `1e-6`    |
| `max_steps`                  | 30        |
| `beta` (KL)                  | 0.04      |
| `temperature`                | 0.8       |
| `top_p`                      | 0.95      |
| `max_completion_length`      | 256 tok   |

Dtype is `float32` because MPS lacks reliable bf16 for Qwen3 at the time of
writing; on CUDA we use bf16.

## 6. Evaluation protocol

We construct a **deterministic** evaluation rollout: same env, same
`seed=0`, same episode order (`sequential=True`). We then run *two*
policies through it back-to-back:

1. **Baseline** — the un-fine-tuned `Qwen3-0.6B`.
2. **Trained** — the GRPO checkpoint produced by §5.

Reported metrics:

* `mean_reward` (overall),
* per-component means (drives `reward_components.png`),
* the full per-episode reward arrays (drives `baseline_vs_trained.png` and
  `reward_distribution.png`).

## 7. What we expected, and why it matters

`Qwen3-0.6B` out-of-the-box almost never produces well-formed JSON in this
schema — it tends to think out loud or to verbose-summarise. After even a
few dozen GRPO steps with our rule-based reward, the policy concentrates
on the format that maximises reward: short JSON with grounded reasons.

That's exactly the shape we want for an LLM-flavoured ranker: easy to
parse, hard to fabricate, and graded on the same axes a recruiter would
care about (right decision, well-calibrated score, grounded reasons).

## 8. Failure modes & guards

| Risk                                       | Guard                                                       |
| ------------------------------------------ | ----------------------------------------------------------- |
| Model collapses to single, gameable output | Reward components 4-6 penalise low-diversity, copy-paste.   |
| KL goes to infinity (gibberish)            | `beta = 0.04` plus low LR (`1e-6`) keep policy near base.   |
| Eval set leakage                           | Same seed, same env, but no parameter updates during eval.  |
| Reward hacking on `length_penalty`         | Linear, not exponential, decay; component weight only 0.05. |
| `num_generations` not dividing batch       | Auto-adjustment in `train.py` (see comment).                |

## 9. Publishing the model

The final cell of the notebook (and the `--push-to-hub` flag of `train.py`)
calls:

```python
trainer.model.push_to_hub("williyam/redrob-qwen-grpo")
tokenizer.push_to_hub("williyam/redrob-qwen-grpo")
```

A model card is auto-generated by TRL/Transformers; we additionally commit
the eval metrics JSON and the four plots so the Hub repo is self-contained.
