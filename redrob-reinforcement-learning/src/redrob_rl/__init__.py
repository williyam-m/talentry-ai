"""
redrob_rl
=========

Reinforcement-Learning environment for the Redrob / Talentry-AI candidate
ranking task. Used to GRPO-fine-tune Qwen3-0.6B into ``redrob-qwen-grpo``.

Public API
----------
- ``CandidateRankEnv``      - the RL environment (gym-like API)
- ``RuleBasedRewardModel``  - deterministic, rule-based reward function
- ``DatasetBuilder``        - turns Redrob candidate JSONL + JD into prompts
"""

from .env import CandidateRankEnv, EnvStep
from .reward import RuleBasedRewardModel, RewardBreakdown
from .dataset import DatasetBuilder, PromptSample

__all__ = [
    "CandidateRankEnv",
    "EnvStep",
    "RuleBasedRewardModel",
    "RewardBreakdown",
    "DatasetBuilder",
    "PromptSample",
]

__version__ = "0.1.0"
