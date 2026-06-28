"""
Reinforcement-Learning environment for the Redrob candidate ranking task.

This is a *single-turn* contextual-bandit-style environment with a Gymnasium-
compatible API (``reset`` / ``step``). At each episode, the environment:

    1. Samples a (prompt, gold_decision, gold_score, context) tuple from a
       dataset built by :class:`redrob_rl.dataset.DatasetBuilder`.
    2. Hands the prompt to the policy as the observation.
    3. Accepts the model's text completion as the action.
    4. Scores the completion with :class:`RuleBasedRewardModel`.
    5. Returns ``(obs, reward, terminated=True, truncated=False, info)``.

The same environment is consumed two ways:

* Episode-based rollout for **baseline evaluation** (see ``rollout``).
* Inside TRL's ``GRPOTrainer`` via the rule-based reward callable produced
  by :func:`redrob_rl.reward.make_trl_reward_fn`.

Why a Gym-style API even though TRL drives training?
----------------------------------------------------
Because the assignment explicitly asks for a *Reinforcement Learning
environment*. A clean ``reset`` / ``step`` boundary lets us:

* Run the baseline (pre-training) policy and the GRPO-trained policy through
  identical rollout code for a like-for-like comparison plot.
* Plug-in a different policy / sampler later without touching the reward.
* Inspect per-step ``info`` dicts for the reward breakdown (used by the
  reward-component bar chart in the notebook).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .dataset import PromptSample
from .reward import RewardBreakdown, RuleBasedRewardModel


# --------------------------------------------------------------------------- #
# Episode step
# --------------------------------------------------------------------------- #

@dataclass
class EnvStep:
    """One environment transition. Mirrors the Gymnasium step tuple but
    typed for clarity in notebooks."""

    observation: str
    reward: float
    terminated: bool = True
    truncated: bool = False
    info: Dict[str, Any] = field(default_factory=dict)

    def as_tuple(self) -> Tuple[str, float, bool, bool, Dict[str, Any]]:
        return (
            self.observation,
            self.reward,
            self.terminated,
            self.truncated,
            self.info,
        )


# --------------------------------------------------------------------------- #
# Environment
# --------------------------------------------------------------------------- #

class CandidateRankEnv:
    """
    Gymnasium-style environment over a list of :class:`PromptSample`.

    Parameters
    ----------
    samples : list[PromptSample]
        The corpus of (prompt, gold-label, gold-score, context) tuples.
    reward_model : RuleBasedRewardModel
        Rule-based reward function. See :mod:`redrob_rl.reward`.
    seed : int
        RNG seed for episode sampling.
    sequential : bool
        If True, iterate the dataset in order (useful for deterministic
        evaluation runs). If False, sample uniformly at random.
    """

    metadata = {"render_modes": ["text"]}

    def __init__(
        self,
        samples: List[PromptSample],
        reward_model: RuleBasedRewardModel,
        *,
        seed: int = 0,
        sequential: bool = False,
    ) -> None:
        if not samples:
            raise ValueError("CandidateRankEnv needs at least one sample.")
        self._samples = list(samples)
        self._reward_model = reward_model
        self._rng = random.Random(seed)
        self._sequential = sequential
        self._cursor: int = 0
        self._current: Optional[PromptSample] = None
        # rolling stats for plotting
        self.episode_rewards: List[float] = []
        self.episode_breakdowns: List[RewardBreakdown] = []

    # ---- Gymnasium-ish ---------------------------------------------------- #

    @property
    def n_samples(self) -> int:
        return len(self._samples)

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        index: Optional[int] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        if seed is not None:
            self._rng = random.Random(seed)
            self._cursor = 0
        if index is not None:
            self._current = self._samples[index % len(self._samples)]
        elif self._sequential:
            self._current = self._samples[self._cursor % len(self._samples)]
            self._cursor += 1
        else:
            self._current = self._rng.choice(self._samples)
        info = {
            "candidate_id": self._current.candidate_id,
            "gold_decision": self._current.decision,
            "gold_score": self._current.score,
        }
        return self._current.prompt, info

    def step(self, action_text: str) -> EnvStep:
        if self._current is None:
            raise RuntimeError("Call reset() before step().")
        reward, bd = self._reward_model(
            action_text,
            gold_decision=self._current.decision,
            gold_score=float(self._current.score),
            context_text=self._current.context,
        )
        self.episode_rewards.append(float(reward))
        self.episode_breakdowns.append(bd)
        info = {
            "candidate_id": self._current.candidate_id,
            "gold_decision": self._current.decision,
            "gold_score": self._current.score,
            "reward_breakdown": bd.as_dict(),
            "completion_preview": (action_text or "")[:200],
        }
        step = EnvStep(
            observation=self._current.prompt,
            reward=float(reward),
            terminated=True,
            truncated=False,
            info=info,
        )
        self._current = None
        return step

    def render(self) -> str:
        if self._current is None:
            return "<no active episode>"
        return self._current.prompt

    def close(self) -> None:
        return None


# --------------------------------------------------------------------------- #
# Roll-out helper (used for baseline vs trained comparison)
# --------------------------------------------------------------------------- #

PolicyFn = Callable[[str], str]
"""A policy is anything that takes a prompt string and returns a completion."""


def rollout(
    env: CandidateRankEnv,
    policy: PolicyFn,
    *,
    n_episodes: int = 32,
    seed: int = 0,
) -> Dict[str, Any]:
    """
    Run ``n_episodes`` of the environment under ``policy``.

    Returns
    -------
    dict with keys
        ``rewards``       - list[float], one per episode
        ``mean_reward``   - float
        ``breakdowns``    - list[dict], reward-component breakdown per episode
        ``decisions``     - list[(gold, predicted_completion)]
    """
    env._rng = random.Random(seed)  # deterministic comparison
    rewards: List[float] = []
    breakdowns: List[Dict[str, float]] = []
    decisions: List[Tuple[str, str]] = []

    for ep in range(n_episodes):
        obs, info = env.reset(index=ep if env._sequential else None)
        completion = policy(obs)
        step = env.step(completion)
        rewards.append(step.reward)
        breakdowns.append(step.info["reward_breakdown"])
        decisions.append((info["gold_decision"], completion[:200]))

    mean = sum(rewards) / max(len(rewards), 1)
    return {
        "rewards": rewards,
        "mean_reward": float(mean),
        "breakdowns": breakdowns,
        "decisions": decisions,
    }
