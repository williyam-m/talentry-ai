"""
Plotting helpers used by the GRPO notebook.

Every plot is saved to ``plots/`` as a PNG with explicit axis labels and
units. The notebook commits these files alongside the notebook itself so
the reader sees the charts in the repo without re-running training.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import matplotlib.pyplot as plt
import numpy as np


def _ensure_dir(p: Path) -> Path:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# --------------------------------------------------------------------------- #
# Training-time plots (from TRL log_history)
# --------------------------------------------------------------------------- #

def plot_training_curves(
    log_history: Sequence[dict],
    out_path: Path,
    *,
    title: str = "GRPO training curves",
) -> Path:
    """Plot reward and loss vs training step on twin y-axes."""
    steps: List[int] = []
    rewards: List[float] = []
    losses: List[float] = []
    klds: List[float] = []
    for row in log_history:
        if "step" not in row:
            continue
        if "reward" in row:
            steps.append(int(row["step"]))
            rewards.append(float(row["reward"]))
        if "loss" in row:
            losses.append(float(row["loss"]))
        if "kl" in row:
            klds.append(float(row["kl"]))

    fig, ax1 = plt.subplots(figsize=(8.5, 4.8), dpi=140)
    ax2 = ax1.twinx()

    if steps and rewards:
        ax1.plot(steps, rewards, color="#1f77b4", lw=2, marker="o",
                 ms=4, label="mean reward")
    if losses:
        s_loss = list(range(1, len(losses) + 1))
        ax2.plot(s_loss, losses, color="#d62728", lw=1.5, ls="--",
                 marker="x", ms=4, label="loss")

    ax1.set_xlabel("Training step (logged optimizer updates)")
    ax1.set_ylabel("Mean reward [0, 1]  ← rule-based reward model",
                   color="#1f77b4")
    ax2.set_ylabel("Loss (GRPO policy loss, lower is better)",
                   color="#d62728")
    ax1.tick_params(axis="y", labelcolor="#1f77b4")
    ax2.tick_params(axis="y", labelcolor="#d62728")
    ax1.grid(alpha=0.25)
    ax1.set_title(title)
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="lower right",
               frameon=False, fontsize=9)
    fig.tight_layout()
    out_path = _ensure_dir(out_path)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
# Baseline vs trained reward distributions
# --------------------------------------------------------------------------- #

def plot_baseline_vs_trained(
    baseline_rewards: Sequence[float],
    trained_rewards: Sequence[float],
    out_path: Path,
    *,
    title: str = "Reward per episode: baseline vs GRPO-trained",
) -> Path:
    """Side-by-side per-episode reward comparison (same axes)."""
    fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=140)
    eps = np.arange(1, max(len(baseline_rewards), len(trained_rewards)) + 1)

    if baseline_rewards:
        ax.plot(eps[: len(baseline_rewards)], baseline_rewards,
                color="#7f7f7f", lw=1.5, marker="o", ms=4,
                label=f"baseline (mean={np.mean(baseline_rewards):.3f})")
    if trained_rewards:
        ax.plot(eps[: len(trained_rewards)], trained_rewards,
                color="#2ca02c", lw=2, marker="s", ms=4,
                label=f"GRPO-trained (mean={np.mean(trained_rewards):.3f})")

    ax.set_xlabel("Episode index (deterministic eval rollout)")
    ax.set_ylabel("Rule-based reward [0, 1]")
    ax.set_ylim(0.0, 1.05)
    ax.grid(alpha=0.25)
    ax.set_title(title)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    fig.tight_layout()
    out_path = _ensure_dir(out_path)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
# Reward component breakdown
# --------------------------------------------------------------------------- #

REWARD_COMPONENTS = [
    "format_valid",
    "decision_match",
    "score_alignment",
    "reason_quality",
    "length_penalty",
    "no_hallucination",
]


def _avg_components(
    breakdowns: Iterable[dict],
) -> Dict[str, float]:
    rows = list(breakdowns)
    if not rows:
        return {c: 0.0 for c in REWARD_COMPONENTS}
    return {
        c: float(np.mean([r.get(c, 0.0) for r in rows]))
        for c in REWARD_COMPONENTS
    }


def plot_reward_components(
    baseline_breakdowns: Sequence[dict],
    trained_breakdowns: Sequence[dict],
    out_path: Path,
    *,
    title: str = "Mean reward by component: baseline vs trained",
) -> Path:
    base = _avg_components(baseline_breakdowns)
    trnd = _avg_components(trained_breakdowns)

    x = np.arange(len(REWARD_COMPONENTS))
    w = 0.38
    fig, ax = plt.subplots(figsize=(9.0, 4.8), dpi=140)
    ax.bar(x - w / 2, [base[c] for c in REWARD_COMPONENTS],
           width=w, color="#7f7f7f", label="baseline")
    ax.bar(x + w / 2, [trnd[c] for c in REWARD_COMPONENTS],
           width=w, color="#2ca02c", label="GRPO-trained")

    ax.set_xticks(x)
    ax.set_xticklabels(REWARD_COMPONENTS, rotation=20, ha="right")
    ax.set_xlabel("Reward component (rule-based)")
    ax.set_ylabel("Mean component value [0, 1]")
    ax.set_ylim(0.0, 1.05)
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    fig.tight_layout()
    out_path = _ensure_dir(out_path)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
# Reward distribution histogram (extra diagnostic)
# --------------------------------------------------------------------------- #

def plot_reward_histogram(
    baseline_rewards: Sequence[float],
    trained_rewards: Sequence[float],
    out_path: Path,
    *,
    title: str = "Reward distribution: baseline vs GRPO-trained",
) -> Path:
    fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=140)
    bins = np.linspace(0.0, 1.0, 21)
    if baseline_rewards:
        ax.hist(baseline_rewards, bins=bins, alpha=0.55, color="#7f7f7f",
                label=f"baseline (n={len(baseline_rewards)})")
    if trained_rewards:
        ax.hist(trained_rewards, bins=bins, alpha=0.55, color="#2ca02c",
                label=f"GRPO-trained (n={len(trained_rewards)})")
    ax.set_xlabel("Reward bucket [0, 1]")
    ax.set_ylabel("Number of episodes (count)")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    fig.tight_layout()
    out_path = _ensure_dir(out_path)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path
