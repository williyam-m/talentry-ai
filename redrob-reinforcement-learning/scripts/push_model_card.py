"""
Build a production-grade Hugging Face model card for ``williyam/redrob-qwen-grpo``
from the live ``outputs/eval_compare.json`` numbers and push it to the Hub.

We assemble the card with ``huggingface_hub.ModelCard`` so the YAML metadata
block is validated, then ``card.push_to_hub("williyam/redrob-qwen-grpo")``.

Run after ``scripts/eval_compare.py`` (which produces eval_compare.json).
"""

from __future__ import annotations

import json
from pathlib import Path

from huggingface_hub import HfApi, ModelCard, ModelCardData, upload_file


HERE = Path(__file__).resolve().parents[1]
REPO_ID = "williyam/redrob-qwen-grpo"
# Prefer the richer eval_compare.json if present (full per-component data);
# fall back to the live eval_metrics.json that train.py emits at the end of
# every run. Both files have the same shape for the fields we care about.
EVAL_JSON_PRIMARY = HERE / "outputs" / "eval_compare.json"
EVAL_JSON_FALLBACK = HERE / "outputs" / "eval_metrics.json"
PLOTS = [
    "training_curves.png",
    "baseline_vs_trained.png",
    "reward_components.png",
    "reward_distribution.png",
]


def _fmt(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}f}"


def _delta(a: float, b: float, digits: int = 3) -> str:
    d = b - a
    sign = "+" if d >= 0 else ""
    return f"{sign}{d:.{digits}f}"


def build_card(eval_data: dict) -> ModelCard:
    base = eval_data["baseline"]
    trnd = eval_data["trained"]
    bc = base["components_mean"]
    tc = trnd["components_mean"]

    components_rows = []
    for k in [
        "format_valid",
        "decision_match",
        "score_alignment",
        "reason_quality",
        "length_penalty",
        "no_hallucination",
        "total",
    ]:
        if k in bc and k in tc:
            components_rows.append(
                f"| `{k}` | {_fmt(bc[k])} | {_fmt(tc[k])} | {_delta(bc[k], tc[k])} |"
            )
    components_table = "\n".join(components_rows)

    metadata = ModelCardData(
        language="en",
        license="mit",
        library_name="transformers",
        pipeline_tag="text-generation",
        tags=[
            "qwen3",
            "qwen3-0.6b",
            "grpo",
            "reinforcement-learning",
            "trl",
            "candidate-ranking",
            "explainable-ai",
            "talentry-ai",
            "redrob",
            "hackathon",
            "open-source",
        ],
        base_model="Qwen/Qwen3-0.6B",
        datasets=["custom-redrob-candidates"],  # synthetic, distilled from the JD+50 candidates
        metrics=["reward"],
    )

    text = f"""---
{metadata.to_yaml()}
---

# redrob-qwen-grpo

> **`Qwen/Qwen3-0.6B` → GRPO-fine-tuned for explainable candidate ranking, under a rule-based reward model (no LLM-as-a-judge).**

[![Open in Spaces](https://img.shields.io/badge/%F0%9F%A4%97%20Live%20demo-talentry--ai-FFD21E)](https://huggingface.co/spaces/williyam/talentry-ai)
[![GitHub](https://img.shields.io/badge/GitHub-talentry--ai-181717?logo=github&logoColor=white)](https://github.com/williyam-m/talentry-ai)
[![License: MIT](https://img.shields.io/badge/license-MIT-22C55E.svg)](https://github.com/williyam-m/talentry-ai/blob/main/LICENSE)

This is the **open-source side-quest** of the [Talentry-AI](https://github.com/williyam-m/talentry-ai)
submission to the **Redrob × Hack2Skill — India Runs** Data & AI Challenge.

The base Talentry-AI ranker is fully deterministic and runs with **0 LLM calls**.
This checkpoint exists for anyone who *wants* an LLM-flavoured candidate ranker
that has been trained against the same rule-based rubric Talentry-AI uses to
audit its own decisions. The Talentry-AI submission itself does **not** depend on
this model.

---

## Headline results

| Metric                        | Baseline (`Qwen/Qwen3-0.6B`) | `redrob-qwen-grpo` | Δ |
| ----------------------------- | --------------------------- | ------------------ | ------ |
| Mean rule-based reward `[0,1]` | **{_fmt(base["mean_reward"])}** | **{_fmt(trnd["mean_reward"])}** | **{_delta(base["mean_reward"], trnd["mean_reward"])}** |
| Eval episodes                 | {eval_data["n_episodes"]}                 | {eval_data["n_episodes"]}        | — |
| Hardware                      | Apple M1 Pro 16 GB · MPS    | Apple M1 Pro 16 GB · MPS | — |
| Eval `max_new_tokens`         | {eval_data["max_new_tokens"]}                          | {eval_data["max_new_tokens"]}                 | — |

The same deterministic eval rollout (`seed=0`, sequential, identical prompts)
is used for both rows so the comparison is fair.

## Per-component improvement (rule-based reward, mean over eval episodes)

| Reward component   | Baseline | Trained | Δ |
| ------------------ | -------- | ------- | -- |
{components_table}

> All components are in `[0, 1]`. `total` is the weighted convex combination
> (see [`reward.py`](https://github.com/williyam-m/talentry-ai/blob/main/redrob-reinforcement-learning/src/redrob_rl/reward.py)).

---

## Quick usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

tok = AutoTokenizer.from_pretrained("williyam/redrob-qwen-grpo")
mdl = AutoModelForCausalLM.from_pretrained(
    "williyam/redrob-qwen-grpo", dtype=torch.float32
).eval()

system = (
    "You are RedRob, an explainable candidate-ranking assistant. "
    "Decide whether the candidate should be SHORTLISTED for the role. "
    "Respond with a single JSON object: "
    '{{"decision":"shortlist"|"reject","score":0..1,"reasons":[..]}}.'
)
user = (
    "[JOB DESCRIPTION]\\n<your JD here>\\n\\n"
    "[CANDIDATE]\\n<candidate profile>"
)

prompt = tok.apply_chat_template(
    [
        {{"role": "system", "content": system}},
        {{"role": "user", "content": user}},
    ],
    tokenize=False,
    add_generation_prompt=True,
)
inputs = tok(prompt, return_tensors="pt")
out = mdl.generate(**inputs, max_new_tokens=512, do_sample=False)
print(tok.decode(out[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True))
```

The model is expected to return:

```json
{{
  "decision": "shortlist" | "reject",
  "score": 0.0-1.0,
  "reasons": ["short, grounded bullet", "..."]
}}
```

---

## Training summary

| Aspect                       | Value                                                            |
| ---------------------------- | ---------------------------------------------------------------- |
| Base model                   | `Qwen/Qwen3-0.6B` (600M params, Qwen3 chat template)             |
| Algorithm                    | GRPO (TRL `GRPOTrainer`)                                         |
| Reward signal                | **Rule-based** (no LLM judge): six interpretable components       |
| Reward components            | `format_valid`, `decision_match`, `score_alignment`, `reason_quality`, `length_penalty`, `no_hallucination` |
| Optimiser steps              | 10 (deliberately short — sample-efficient demo on a laptop GPU)  |
| `num_generations`            | 2 (group size; 2-arm advantage estimate)                         |
| KL coefficient `β`           | 0.04                                                             |
| Learning rate                | 5e-6                                                             |
| Sampling temperature / top-p | 1.0 / 0.95                                                       |
| Max completion length        | 96 tokens (training); 512 tokens (eval, this card)               |
| Hardware                     | Apple M1 Pro 16 GB · MPS (`bf16=False`, `fp16=False`, `fp32`)    |
| Gradient checkpointing       | Yes (`use_reentrant=False`)                                      |
| Training wall-clock          | ~4.5 minutes for 10 steps                                        |

Full training config: [`configs/grpo_qwen3_0p6b.yaml`](https://github.com/williyam-m/talentry-ai/blob/main/redrob-reinforcement-learning/configs/grpo_qwen3_0p6b.yaml).

## Reward model (no LLM judge)

Every completion is graded by [`RuleBasedRewardModel`](https://github.com/williyam-m/talentry-ai/blob/main/redrob-reinforcement-learning/src/redrob_rl/reward.py)
on six components, each clipped to `[0, 1]`:

| Component         | What it measures                                                          |
| ----------------- | ------------------------------------------------------------------------- |
| `format_valid`    | Output parses as `{{"decision","score","reasons"}}` JSON.                  |
| `decision_match`  | Matches gold `"shortlist" / "reject"` label.                              |
| `score_alignment` | `1 - │pred_score - gold_score│`.                                          |
| `reason_quality`  | 2–5 short, diverse reasons that aren't copy-pasted from the input.        |
| `length_penalty`  | Stays inside a sensible character budget.                                 |
| `no_hallucination`| Proper nouns / numbers in reasons all appear in the JD or candidate text. |

Total reward = convex combination (weights documented in the dataclass), so
`total ∈ [0, 1]`.

---

## Plots

The four training plots are committed to this repo and rendered inline below:

<p align="center">
  <img src="https://huggingface.co/williyam/redrob-qwen-grpo/resolve/main/training_curves.png" alt="Training curves" width="48%"/>
  <img src="https://huggingface.co/williyam/redrob-qwen-grpo/resolve/main/baseline_vs_trained.png" alt="Baseline vs trained" width="48%"/>
</p>
<p align="center">
  <img src="https://huggingface.co/williyam/redrob-qwen-grpo/resolve/main/reward_components.png" alt="Reward components" width="48%"/>
  <img src="https://huggingface.co/williyam/redrob-qwen-grpo/resolve/main/reward_distribution.png" alt="Reward distribution" width="48%"/>
</p>

| File                          | Description                                                            |
| ----------------------------- | ---------------------------------------------------------------------- |
| `training_curves.png`         | Mean reward `[0,1]` (left axis) + GRPO loss (right axis) vs train step.|
| `baseline_vs_trained.png`     | Per-episode reward on the same eval rollout, baseline vs trained.       |
| `reward_components.png`       | Mean value of each rule-based reward component, baseline vs trained.    |
| `reward_distribution.png`     | Histogram of episode rewards across the eval rollout.                   |

---

## Intended use

* **Educational / research** — show how GRPO with a rule-based reward
  shapes a small open-source LLM toward a structured JSON output schema
  for a real-world hiring-adjacent task.
* **Drop-in component** — for anyone who wants to plug an LLM ranker into
  a candidate-shortlisting pipeline and get an auditable JSON `{{decision,
  score, reasons}}` response.
* **Reference implementation** — the entire training loop, env, and reward
  model are open-source under MIT
  ([source](https://github.com/williyam-m/talentry-ai/tree/main/redrob-reinforcement-learning)).

## Out-of-scope / limitations

* **Not a substitute for human review.** This model produces a *score* and
  *reasons*; final hiring decisions must always involve a human reviewer.
* **Trained on a 30-sample distilled fixture** of the Redrob hackathon's
  candidate pool — it is *not* trained on the full 100K candidate
  population and will not generalise to arbitrary new JDs without
  fine-tuning on your own data.
* **Short training run** (10 GRPO steps). The reward shapes can move
  meaningfully more with longer training; this checkpoint is the
  hackathon-submission burst, not a SOTA result.
* **Single-language** (English).
* **Possible biases** inherited from `Qwen/Qwen3-0.6B`'s pre-training data
  and from the synthetic dataset of 50 Redrob candidates.
* **Honeypot resistance** is provided by Talentry-AI's deterministic
  pipeline, not by this checkpoint — the LLM here cannot, by itself,
  detect "8 years at a 3-year-old company"-style impossibilities.

## Citation

If you use this checkpoint, please cite:

```bibtex
@misc{{redrob_qwen_grpo_2026,
  title  = {{redrob-qwen-grpo: GRPO fine-tune of Qwen3-0.6B for explainable candidate ranking}},
  author = {{Williyam M}},
  year   = {{2026}},
  url    = {{https://huggingface.co/williyam/redrob-qwen-grpo}},
  note   = {{Open-source artifact from the Talentry-AI / Redrob × Hack2Skill - India Runs submission.}}
}}
```

## License

MIT — see the [Talentry-AI LICENSE](https://github.com/williyam-m/talentry-ai/blob/main/LICENSE).

## Acknowledgements

* `Qwen/Qwen3-0.6B` from the Qwen team.
* `trl` for the GRPO implementation.
* `Redrob × Hack2Skill — India Runs` for the JD + 50-candidate fixture.
"""

    return ModelCard(text)


def _coerce_eval_data(raw: dict) -> dict:
    """Normalise either eval_compare.json or eval_metrics.json into the
    schema build_card() expects."""
    if "baseline" in raw and "trained" in raw:
        return raw
    # train.py's eval_metrics.json: flat schema → wrap it.
    base_mean = raw.get("baseline_mean_reward", 0.0)
    trained_mean = raw.get("trained_mean_reward", 0.0)
    return {
        "device": raw.get("device", "mps"),
        "n_episodes": raw.get("n_samples", 10),
        "eval_seed": 0,
        "max_new_tokens": 384,
        "uplift": raw.get("uplift", trained_mean - base_mean),
        "baseline": {
            "model": "Qwen/Qwen3-0.6B",
            "mean_reward": float(base_mean),
            "rewards": [],
            "components_mean": raw.get("baseline_components_mean", {
                "total": float(base_mean)
            }),
            "wall_seconds": 0.0,
        },
        "trained": {
            "model": "williyam/redrob-qwen-grpo",
            "mean_reward": float(trained_mean),
            "rewards": [],
            "components_mean": raw.get("trained_components_mean", {
                "total": float(trained_mean)
            }),
            "wall_seconds": raw.get("train_seconds", 0.0),
        },
    }


def main() -> None:
    src = EVAL_JSON_PRIMARY if EVAL_JSON_PRIMARY.exists() else EVAL_JSON_FALLBACK
    if not src.exists():
        raise FileNotFoundError(
            f"Neither {EVAL_JSON_PRIMARY} nor {EVAL_JSON_FALLBACK} found. "
            "Run scripts/eval_compare.py or the training pipeline first."
        )
    print(f"[card] using metrics from {src}")
    eval_data = _coerce_eval_data(json.loads(src.read_text()))
    card = build_card(eval_data)
    card_path = HERE / "outputs" / "model_card.md"
    card_path.write_text(card.content)
    print(f"[card] wrote {card_path}")

    print(f"[card] pushing to {REPO_ID} …")
    card.push_to_hub(REPO_ID, commit_message="docs: production-ready model card with eval metrics")
    # Also upload the four plots so they render on the model page.
    api = HfApi()
    for plot in PLOTS:
        p = HERE / "plots" / plot
        if p.exists():
            api.upload_file(
                path_or_fileobj=str(p),
                path_in_repo=plot,
                repo_id=REPO_ID,
                commit_message=f"viz: {plot}",
            )
            print(f"[card] uploaded {plot}")
    # And the eval JSON for reproducibility.
    api.upload_file(
        path_or_fileobj=str(src),
        path_in_repo=src.name,
        repo_id=REPO_ID,
        commit_message=f"metrics: {src.name} (baseline vs trained)",
    )
    print("[card] done. https://huggingface.co/" + REPO_ID)


if __name__ == "__main__":
    main()
