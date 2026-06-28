"""
Re-evaluate the trained ``redrob-qwen-grpo`` checkpoint against the base
``Qwen/Qwen3-0.6B`` on the *same* rollout, with a roomy generation budget
so the policy actually has space to finish its JSON output.

This is what powers the production "before/after" numbers in the README
and on the Hugging Face model card. Outputs:

  * outputs/eval_compare.json   <- baseline vs trained metrics (full breakdown)
  * plots/baseline_vs_trained.png
  * plots/reward_components.png
  * plots/reward_distribution.png

Run from the project root:

    cd talentry-ai/redrob-reinforcement-learning
    source ../.venv-rl/bin/activate
    PYTHONPATH=src python scripts/eval_compare.py
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Dict, List

import torch
import yaml
from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

from redrob_rl.dataset import DatasetBuilder, SYSTEM_PROMPT
from redrob_rl.env import CandidateRankEnv, rollout
from redrob_rl.plotting import (
    plot_baseline_vs_trained,
    plot_reward_components,
    plot_reward_histogram,
)
from redrob_rl.reward import RuleBasedRewardModel


HERE = Path(__file__).resolve().parents[1]
CONFIG = HERE / "configs" / "grpo_qwen3_0p6b.yaml"

BASE_MODEL = "Qwen/Qwen3-0.6B"
TRAINED_MODEL = "williyam/redrob-qwen-grpo"
# Big enough so the policy can finish the JSON without being clipped.
EVAL_MAX_NEW_TOKENS = 384
EVAL_N_EPISODES = 12
EVAL_SEED = 0


def _device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _strip_thinking(text: str) -> str:
    return re.sub(r"<think>[\s\S]*?</think>", "", text or "", flags=re.IGNORECASE)


def _format_chat(tokenizer, prompt: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )


def _make_policy(model, tokenizer, device, *, max_new_tokens: int):
    model.eval()

    @torch.no_grad()
    def policy(prompt: str) -> str:
        text = _format_chat(tokenizer, prompt)
        inputs = tokenizer(
            text, return_tensors="pt", truncation=True, max_length=1024
        ).to(device)
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
        gen = out[0, inputs["input_ids"].shape[1]:]
        return tokenizer.decode(gen, skip_special_tokens=True)

    return policy


def evaluate(model_id: str, samples, reward_model, device) -> Dict:
    print(f"\n[eval] loading {model_id} on {device} …")
    tok = AutoTokenizer.from_pretrained(model_id)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    mdl = AutoModelForCausalLM.from_pretrained(
        model_id, dtype=torch.float32, attn_implementation="eager"
    ).to(device)
    policy = _make_policy(mdl, tok, device, max_new_tokens=EVAL_MAX_NEW_TOKENS)
    env = CandidateRankEnv(samples, reward_model, sequential=True)
    t0 = time.time()
    res = rollout(env, lambda p: _strip_thinking(policy(p)),
                  n_episodes=EVAL_N_EPISODES, seed=EVAL_SEED)
    dt = time.time() - t0
    del mdl
    if device.type == "mps":
        torch.mps.empty_cache()
    elif device.type == "cuda":
        torch.cuda.empty_cache()
    res["wall_seconds"] = dt
    print(f"[eval] {model_id} mean reward {res['mean_reward']:.4f} "
          f"({dt:.1f}s, {EVAL_N_EPISODES} eps)")
    return res


def main() -> None:
    set_seed(7)
    device = _device()
    cfg = yaml.safe_load(CONFIG.open())
    builder = DatasetBuilder(
        candidates_path=(HERE / cfg["dataset"]["candidates_path"]).resolve(),
        jd_path=(HERE / cfg["dataset"]["jd_path"]).resolve(),
        top_k=cfg["dataset"]["top_k"],
        max_samples=cfg["dataset"]["max_samples"],
        seed=cfg["dataset"]["seed"],
        balance_classes=cfg["dataset"]["balance_classes"],
    )
    samples = builder.build()
    reward_model = RuleBasedRewardModel(**{
        k: v for k, v in cfg["reward"].items()
        if k in RuleBasedRewardModel.__dataclass_fields__
    })
    print(f"[eval] {len(samples)} samples "
          f"(pos={sum(1 for s in samples if s.decision=='shortlist')})")

    # Resumable: cache each side's rollout so we don't re-eval if interrupted.
    cache_dir = HERE / "outputs" / "_eval_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    base_cache = cache_dir / f"baseline_n{EVAL_N_EPISODES}_m{EVAL_MAX_NEW_TOKENS}.json"
    trnd_cache = cache_dir / f"trained_n{EVAL_N_EPISODES}_m{EVAL_MAX_NEW_TOKENS}.json"

    def _run_cached(cache_path: Path, model_id: str):
        if cache_path.exists():
            print(f"[eval] cache hit: {cache_path.name}")
            return json.loads(cache_path.read_text())
        res = evaluate(model_id, samples, reward_model, device)
        # rollout() returns numpy / dict objects -> coerce to JSON-safe
        safe = {
            "mean_reward": float(res["mean_reward"]),
            "rewards": [float(r) for r in res["rewards"]],
            "breakdowns": [
                {k: float(v) for k, v in b.items()} for b in res["breakdowns"]
            ],
            "wall_seconds": float(res["wall_seconds"]),
        }
        cache_path.write_text(json.dumps(safe, indent=2))
        return safe

    baseline = _run_cached(base_cache, BASE_MODEL)
    trained = _run_cached(trnd_cache, TRAINED_MODEL)

    # --- plots --- #
    plots_dir = HERE / "plots"
    plots_dir.mkdir(exist_ok=True)
    plot_baseline_vs_trained(
        baseline["rewards"], trained["rewards"],
        plots_dir / "baseline_vs_trained.png",
        title=f"Reward per episode: baseline vs GRPO-trained "
              f"(n={EVAL_N_EPISODES}, seed=0)",
    )
    plot_reward_components(
        baseline["breakdowns"], trained["breakdowns"],
        plots_dir / "reward_components.png",
        title="Mean reward by component (rule-based reward model)",
    )
    plot_reward_histogram(
        baseline["rewards"], trained["rewards"],
        plots_dir / "reward_distribution.png",
        title="Reward distribution across the eval episodes",
    )

    # --- metrics summary --- #
    def _comp_means(breakdowns: List[Dict[str, float]]) -> Dict[str, float]:
        keys = list(breakdowns[0].keys())
        return {k: float(sum(b[k] for b in breakdowns) / len(breakdowns))
                for k in keys}

    summary = {
        "device": str(device),
        "n_episodes": EVAL_N_EPISODES,
        "eval_seed": EVAL_SEED,
        "max_new_tokens": EVAL_MAX_NEW_TOKENS,
        "baseline": {
            "model": BASE_MODEL,
            "mean_reward": baseline["mean_reward"],
            "rewards": baseline["rewards"],
            "components_mean": _comp_means(baseline["breakdowns"]),
            "wall_seconds": baseline["wall_seconds"],
        },
        "trained": {
            "model": TRAINED_MODEL,
            "mean_reward": trained["mean_reward"],
            "rewards": trained["rewards"],
            "components_mean": _comp_means(trained["breakdowns"]),
            "wall_seconds": trained["wall_seconds"],
        },
        "uplift": trained["mean_reward"] - baseline["mean_reward"],
    }
    out = HERE / "outputs" / "eval_compare.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(summary, indent=2))
    print(f"\n[eval] wrote {out}")
    print(json.dumps(
        {k: v for k, v in summary.items() if k not in ("baseline", "trained")},
        indent=2,
    ))
    print("baseline mean reward:", round(summary["baseline"]["mean_reward"], 4))
    print("trained  mean reward:", round(summary["trained"]["mean_reward"], 4))
    print("uplift:               ", round(summary["uplift"], 4))


if __name__ == "__main__":
    main()
