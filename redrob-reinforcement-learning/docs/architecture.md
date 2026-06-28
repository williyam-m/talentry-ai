# `redrob-reinforcement-learning` — Architecture & Design

> The RL playground that powers
> **[`williyam/redrob-qwen-grpo`](https://huggingface.co/williyam/redrob-qwen-grpo)**.

## 1. Goal

Take the Redrob / Talentry-AI candidate-ranking task and turn it into a
single-turn Reinforcement Learning problem so we can **GRPO-fine-tune a
small, open-source LLM** (`Qwen/Qwen3-0.6B`) to produce ranking decisions
that match our production scorer's gold labels — without ever calling
another LLM as a judge.

The shipped artifact is an **open-source checkpoint on the Hugging Face Hub**
that anyone running the Talentry-AI pipeline can pull and reuse.

## 2. High-level architecture

```
                  ┌────────────────────────────────┐
                  │  Talentry-AI production ranker │
                  │  (BM25 + TF-IDF + signals)     │
                  └──────────────┬─────────────────┘
                                 │ gold labels
                                 ▼
 ┌───────────────┐        ┌────────────────┐        ┌───────────────────┐
 │ candidates    │        │ DatasetBuilder │        │ PromptSample list │
 │ .json / .jsonl│ ─────▶ │ (gold labels   │ ─────▶ │ (prompt, decision,│
 │ + JD .txt     │        │  + balancing)  │        │  score, context)  │
 └───────────────┘        └────────────────┘        └─────────┬─────────┘
                                                              │
                          ┌───────────────────────────────────┘
                          ▼
                ┌────────────────────────┐        ┌──────────────────────┐
                │  CandidateRankEnv      │  reward │ RuleBasedRewardModel│
                │  (Gymnasium API)       │ ◀───── │ (no LLM judge)      │
                └─────────┬──────────────┘        └──────────────────────┘
                          │
              ┌───────────┴────────────┐
              ▼                        ▼
     ┌──────────────┐         ┌──────────────────┐
     │ rollout()    │         │  TRL GRPOTrainer │
     │ (eval)       │         │  (Qwen3-0.6B)    │
     └──────┬───────┘         └──────────┬───────┘
            │                            │ trained policy
            ▼                            ▼
     baseline rewards            ┌──────────────────┐
                                 │ outputs/         │
                                 │ redrob-qwen-grpo │ ──▶ HF Hub
                                 └──────────────────┘
            ▼                            ▼
            └─────────────► plots/ (.png) ◀────────┘
```

Each box is one Python module under `src/redrob_rl/`:

| Module          | Responsibility                                                           |
| --------------- | ------------------------------------------------------------------------ |
| `dataset.py`    | Build `PromptSample`s from candidates + JD using the production ranker.  |
| `reward.py`     | Deterministic, rule-based reward (six components, weighted convex sum).  |
| `env.py`        | Gymnasium-style `CandidateRankEnv` + `rollout` helper.                   |
| `plotting.py`   | All chart helpers; every plot is saved as `.png` with labelled axes.     |
| `train.py`      | End-to-end training loop (load → baseline → GRPO → eval → plot → push).  |

## 3. Why a rule-based reward (not an LLM judge)

The hackathon dataset is engineered to fool naive rankers (keyword stuffers,
plain-language seniors, behavioural twins, honeypots). Using an LLM judge
would:

1. Re-introduce the very hallucination class we're trying to eliminate.
2. Make training non-reproducible (judge drift between runs).
3. Add network cost on every step.

Our rule-based reward (`reward.py`) scores six things, each clipped to `[0, 1]`:

| Component         | What it measures                                                            |
| ----------------- | --------------------------------------------------------------------------- |
| `format_valid`    | Output parses as the required `{decision, score, reasons}` JSON object.     |
| `decision_match`  | Predicted decision matches the gold `shortlist` / `reject` label.           |
| `score_alignment` | `1 - |pred_score - gold_score|`.                                            |
| `reason_quality`  | 2–5 short, diverse reasons that aren't copy-pasted from the input.          |
| `length_penalty`  | Stays inside a sensible character budget.                                   |
| `no_hallucination`| Numeric tokens / proper nouns in reasons all appear in the input context.   |

The total reward is the convex combination of all six components (weights
declared on the dataclass) and is **always in `[0, 1]`**.

## 4. The RL environment

`CandidateRankEnv` is a single-turn contextual-bandit-style environment with
the standard Gymnasium API:

```python
env = CandidateRankEnv(samples, RuleBasedRewardModel(), sequential=True)
obs, info = env.reset(index=0)
completion = policy(obs)        # any function: str -> str
step = env.step(completion)     # returns (obs, reward, terminated=True, truncated, info)
```

`info` always contains the full reward breakdown so plots like
`reward_components.png` are produced directly from the env, never from
auxiliary book-keeping that could drift out of sync with training.

The same env powers two flows:

* **Eval** — `rollout(env, policy, n_episodes=N)` for the baseline and the
  GRPO-trained policy, on identical (sequential, seeded) episodes.
* **Training** — TRL’s `GRPOTrainer` consumes the *reward function* the env
  exposes via `make_trl_reward_fn(...)`, so the reward that drives training
  is bit-for-bit the same one used for evaluation.

## 5. GRPO trainer

We use TRL's `GRPOTrainer` (Group Relative Policy Optimisation — the same
algorithm DeepSeek-R1 used). For each prompt we generate **N completions**,
score them with our reward model, then push the policy towards the
top-reward completions while a KL term keeps the policy near the base
`Qwen3-0.6B`.

Key knobs in `configs/grpo_qwen3_0p6b.yaml`:

| Knob                    | Why                                                              |
| ----------------------- | ---------------------------------------------------------------- |
| `num_generations: 4`    | Group size — bigger groups = lower variance, more compute.       |
| `beta: 0.04`            | KL coefficient — keeps language fluent.                          |
| `learning_rate: 1e-6`   | Small LR; we’re shaping, not rewriting.                          |
| `max_steps: 30`         | Tuned for ~10 min on Apple M1 Pro 16 GB.                         |
| `temperature: 0.8`      | Enough diversity to give GRPO a useful spread.                   |
| `dtype: float32`        | MPS does not yet support bf16 reliably for this model.           |
| `attn_implementation: eager` | Avoids the flash-attn dependency on Mac.                    |

## 6. Plots (committed alongside the notebook)

Every figure is saved as a `.png` in `plots/` with explicit axis labels and
units:

| File                         | x-axis                                | y-axis                              |
| ---------------------------- | ------------------------------------- | ----------------------------------- |
| `training_curves.png`        | Training step                         | Mean reward `[0, 1]` *and* GRPO loss|
| `baseline_vs_trained.png`    | Episode index (deterministic rollout) | Rule-based reward `[0, 1]`          |
| `reward_components.png`      | Reward component                      | Mean component value `[0, 1]`       |
| `reward_distribution.png`    | Reward bucket `[0, 1]`                | Number of episodes (count)          |

The baseline and trained runs are plotted **on the same axes** so the
uplift is visually obvious.

## 7. Pushing the model

`train.py` ends with `trainer.model.push_to_hub("williyam/redrob-qwen-grpo")`
using the already-logged-in `huggingface_hub` Python client (no
`huggingface-cli` required). The notebook does exactly the same call from
its final cell.

## 8. How to use the published model

Anyone can `pip install transformers torch` and:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
tok = AutoTokenizer.from_pretrained("williyam/redrob-qwen-grpo")
mdl = AutoModelForCausalLM.from_pretrained("williyam/redrob-qwen-grpo")
```

…and reuse the same prompt schema from `redrob_rl.dataset.SYSTEM_PROMPT`.

Talentry-AI itself does **not** depend on the checkpoint — it's a free
open-source by-product of the RL work, published for the community.

## 9. Reproducibility

* Every seed is explicit (`seed=7` for dataset, `seed=0` for eval rollouts).
* The reward model is pure-Python — no network, no GPU, no randomness.
* `redrob-qwen-grpo/eval_metrics.json` summarises baseline vs trained
  rewards and is committed to the repo.
* `train.py` and the notebook share the *same* `train.main()` entry point,
  so re-running the notebook produces identical artifacts to the CLI run.
