"""
Standalone GRPO training script.

This mirrors the logic of ``notebooks/redrob_qwen_grpo.ipynb`` so the
notebook stays readable. Both call into this module - which means running
the notebook end-to-end and running ``python -m redrob_rl.train`` produce
identical artifacts on disk.

Outputs
-------
- ``outputs/redrob-qwen-grpo/``      LoRA / full weights ready to push
- ``plots/training_curves.png``      reward + loss vs training step
- ``plots/baseline_vs_trained.png``  per-episode reward comparison
- ``plots/reward_components.png``    component-level breakdown
- ``plots/reward_distribution.png``  reward histogram
- ``outputs/eval_metrics.json``      summary metrics
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch
import yaml
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

from .dataset import DatasetBuilder, SYSTEM_PROMPT
from .env import CandidateRankEnv, rollout
from .plotting import (
    plot_baseline_vs_trained,
    plot_reward_components,
    plot_reward_histogram,
    plot_training_curves,
)
from .reward import RuleBasedRewardModel, make_trl_reward_fn


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _load_yaml(p: Path) -> Dict[str, Any]:
    with Path(p).open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _format_chat(tokenizer, prompt: str) -> str:
    """Apply the model's chat template with the RedRob system prompt."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )


def _make_policy(model, tokenizer, device, *, max_new_tokens: int = 200,
                 temperature: float = 0.0):
    """Build a callable ``policy(prompt: str) -> str`` for rollout."""
    model.eval()

    @torch.no_grad()
    def policy(prompt: str) -> str:
        text = _format_chat(tokenizer, prompt)
        inputs = tokenizer(text, return_tensors="pt", truncation=True,
                           max_length=1024).to(device)
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=temperature > 0.0,
            temperature=max(temperature, 0.01),
            top_p=0.95,
            pad_token_id=tokenizer.eos_token_id,
        )
        gen = out[0, inputs["input_ids"].shape[1]:]
        return tokenizer.decode(gen, skip_special_tokens=True)

    return policy


def _strip_thinking(text: str) -> str:
    """Qwen3 likes to emit <think>…</think>; drop it before scoring."""
    return re.sub(r"<think>[\s\S]*?</think>", "", text or "", flags=re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main(cfg_path: str, *, push_to_hub: bool = False) -> Dict[str, Any]:
    here = Path(__file__).resolve().parents[2]   # redrob-reinforcement-learning/
    cfg = _load_yaml(Path(cfg_path))
    plots_dir = here / "plots"
    out_dir = (here / cfg["trainer"]["output_dir"]).resolve()
    plots_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    set_seed(cfg["trainer"].get("seed", 7))
    device = _device()
    print(f"[redrob-rl] device: {device}")

    # ----- 1. dataset ------------------------------------------------------ #
    cand_path = (here / cfg["dataset"]["candidates_path"]).resolve()
    jd_path = (here / cfg["dataset"]["jd_path"]).resolve()
    builder = DatasetBuilder(
        candidates_path=cand_path,
        jd_path=jd_path,
        top_k=cfg["dataset"]["top_k"],
        max_samples=cfg["dataset"]["max_samples"],
        seed=cfg["dataset"]["seed"],
        balance_classes=cfg["dataset"]["balance_classes"],
    )
    samples = builder.build()
    print(f"[redrob-rl] built {len(samples)} samples "
          f"(pos={sum(1 for s in samples if s.decision=='shortlist')})")
    builder.write_jsonl(samples, here / "data" / "processed" / "train.jsonl")

    reward_model = RuleBasedRewardModel(**{
        k: v for k, v in cfg["reward"].items()
        if k in RuleBasedRewardModel.__dataclass_fields__
    })
    env = CandidateRankEnv(samples, reward_model, sequential=True)

    # ----- 2. model + tokenizer ------------------------------------------- #
    model_name = cfg["model"]["name"]
    print(f"[redrob-rl] loading base model: {model_name}")
    dtype = torch.float32 if cfg["model"]["dtype"] == "float32" else torch.bfloat16
    tokenizer = AutoTokenizer.from_pretrained(
        model_name, trust_remote_code=cfg["model"]["trust_remote_code"]
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    base_model = AutoModelForCausalLM.from_pretrained(
        model_name,
        dtype=dtype,
        trust_remote_code=cfg["model"]["trust_remote_code"],
        attn_implementation=cfg["model"].get("attn_implementation", "eager"),
    ).to(device)

    # ----- 3. baseline rollout -------------------------------------------- #
    print("[redrob-rl] running baseline rollout …")
    eval_n = int(cfg["eval"]["n_episodes"])
    baseline_policy = _make_policy(base_model, tokenizer, device,
                                   max_new_tokens=160, temperature=0.0)
    base_eval = rollout(env, lambda p: _strip_thinking(baseline_policy(p)),
                        n_episodes=eval_n, seed=cfg["eval"]["seed"])
    print(f"[redrob-rl] baseline mean reward: {base_eval['mean_reward']:.4f}")

    # ----- 4. GRPO training ------------------------------------------------ #
    from trl import GRPOConfig, GRPOTrainer

    # Build dataset of dicts that TRL will iterate over.
    hf_records = []
    for s in samples:
        hf_records.append({
            "prompt": _format_chat(tokenizer, s.prompt),
            "context": s.context,
            "decision": s.decision,
            "score": float(s.score),
        })
    ds = Dataset.from_list(hf_records)

    reward_fn = make_trl_reward_fn(
        reward_model,
        gold_decisions=[r["decision"] for r in hf_records],
        gold_scores=[r["score"] for r in hf_records],
        contexts=[r["context"] for r in hf_records],
    )

    tcfg = cfg["trainer"]
    # GRPO requires effective batch (per_device * grad_accum) divisible by num_generations.
    eff_bsz = tcfg["per_device_train_batch_size"] * tcfg["gradient_accumulation_steps"]
    ngen = tcfg["num_generations"]
    if eff_bsz % ngen != 0:
        new_ga = max(1, (ngen // tcfg["per_device_train_batch_size"]))
        print(f"[redrob-rl] adjusting gradient_accumulation_steps "
              f"{tcfg['gradient_accumulation_steps']} -> {new_ga}")
        tcfg["gradient_accumulation_steps"] = new_ga

    grpo_kwargs = dict(
        output_dir=str(out_dir),
        per_device_train_batch_size=tcfg["per_device_train_batch_size"],
        gradient_accumulation_steps=tcfg["gradient_accumulation_steps"],
        learning_rate=float(tcfg["learning_rate"]),
        max_steps=int(tcfg["max_steps"]),
        logging_steps=int(tcfg["logging_steps"]),
        save_steps=int(tcfg["save_steps"]),
        num_generations=int(tcfg["num_generations"]),
        max_completion_length=int(tcfg["max_completion_length"]),
        beta=float(tcfg["beta"]),
        temperature=float(tcfg["temperature"]),
        top_p=float(tcfg["top_p"]),
        bf16=bool(tcfg.get("bf16", False)),
        fp16=bool(tcfg.get("fp16", False)),
        gradient_checkpointing=bool(tcfg.get("gradient_checkpointing", False)),
        seed=int(tcfg.get("seed", 7)),
        report_to="none",
        remove_unused_columns=False,
        save_total_limit=1,
    )
    grpo_cfg = GRPOConfig(**grpo_kwargs)

    print("[redrob-rl] starting GRPO training …")
    trainer = GRPOTrainer(
        model=base_model,
        args=grpo_cfg,
        train_dataset=ds,
        processing_class=tokenizer,
        reward_funcs=reward_fn,
    )
    t0 = time.time()
    trainer.train()
    train_secs = time.time() - t0
    print(f"[redrob-rl] training done in {train_secs:.1f}s")

    # Save the fine-tuned policy
    trainer.save_model(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))

    # ----- 5. trained rollout --------------------------------------------- #
    print("[redrob-rl] running trained-policy rollout …")
    trained_policy = _make_policy(trainer.model, tokenizer, device,
                                  max_new_tokens=160, temperature=0.0)
    env_trained = CandidateRankEnv(samples, reward_model, sequential=True)
    trained_eval = rollout(env_trained,
                           lambda p: _strip_thinking(trained_policy(p)),
                           n_episodes=eval_n, seed=cfg["eval"]["seed"])
    print(f"[redrob-rl] trained mean reward:  {trained_eval['mean_reward']:.4f}")

    # ----- 6. plots ------------------------------------------------------- #
    log_history = trainer.state.log_history if hasattr(trainer, "state") else []
    p1 = plot_training_curves(log_history, plots_dir / "training_curves.png",
                              title="GRPO training curves (Qwen3-0.6B → redrob-qwen-grpo)")
    p2 = plot_baseline_vs_trained(
        base_eval["rewards"], trained_eval["rewards"],
        plots_dir / "baseline_vs_trained.png",
        title="Reward per episode: baseline vs GRPO-trained (same eval set)",
    )
    p3 = plot_reward_components(
        base_eval["breakdowns"], trained_eval["breakdowns"],
        plots_dir / "reward_components.png",
        title="Mean reward by component (rule-based reward model)",
    )
    p4 = plot_reward_histogram(
        base_eval["rewards"], trained_eval["rewards"],
        plots_dir / "reward_distribution.png",
        title="Reward distribution across the eval episodes",
    )
    print(f"[redrob-rl] saved plots: {p1.name}, {p2.name}, {p3.name}, {p4.name}")

    # ----- 7. metrics summary --------------------------------------------- #
    metrics = {
        "device": str(device),
        "model": model_name,
        "n_samples": len(samples),
        "baseline_mean_reward": base_eval["mean_reward"],
        "trained_mean_reward": trained_eval["mean_reward"],
        "uplift": trained_eval["mean_reward"] - base_eval["mean_reward"],
        "train_seconds": train_secs,
        "max_steps": int(tcfg["max_steps"]),
        "num_generations": int(tcfg["num_generations"]),
        "log_history_tail": list(log_history)[-5:],
    }
    (here / "outputs" / "eval_metrics.json").parent.mkdir(parents=True, exist_ok=True)
    with (here / "outputs" / "eval_metrics.json").open("w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    print(json.dumps({k: v for k, v in metrics.items()
                      if k != "log_history_tail"}, indent=2))

    # ----- 8. push to HF Hub --------------------------------------------- #
    if push_to_hub:
        print(f"[redrob-rl] pushing to hub: {cfg['hub']['repo_id']}")
        trainer.model.push_to_hub(
            cfg["hub"]["repo_id"],
            private=bool(cfg["hub"].get("private", False)),
            commit_message=cfg["hub"]["commit_message"],
        )
        tokenizer.push_to_hub(
            cfg["hub"]["repo_id"],
            private=bool(cfg["hub"].get("private", False)),
            commit_message=cfg["hub"]["commit_message"] + " (tokenizer)",
        )

    return metrics


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/grpo_qwen3_0p6b.yaml")
    ap.add_argument("--push-to-hub", action="store_true")
    args = ap.parse_args()
    main(args.config, push_to_hub=args.push_to_hub)
