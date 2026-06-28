#!/usr/bin/env bash
# Final per-file commit + push helper for the redrob-reinforcement-learning subproject.
# Run from the repo root (talentry-ai/).
set -e
cd "$(dirname "$0")/../.."

ROOT="redrob-reinforcement-learning"

commit_one () {
  local path="$1"
  local msg="$2"
  if git diff --quiet -- "$path" && git diff --cached --quiet -- "$path" && ! git ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then
    git add -A "$path"
  else
    git add -A "$path"
  fi
  if ! git diff --cached --quiet -- "$path"; then
    git commit -m "$msg" -- "$path"
    echo "✔ committed $path"
  else
    echo "·  nothing to commit for $path"
  fi
}

commit_one "$ROOT/src/redrob_rl/dataset.py" \
  "feat(redrob-rl): tighten system prompt for JSON-only output (+/no_think) so the policy stops emitting prose"

commit_one "$ROOT/src/redrob_rl/sft.py" \
  "feat(redrob-rl): add SFT warm-start with grounded gold JSON answers (standard GRPO recipe — fixes zero-advantage)"

commit_one "$ROOT/src/redrob_rl/train.py" \
  "feat(redrob-rl): wire SFT into the training loop and emit per-component eval metrics"

commit_one "$ROOT/configs/grpo_qwen3_0p6b.yaml" \
  "config(redrob-rl): bump LR/max_steps/temperature for non-zero advantage; add SFT block"

commit_one "$ROOT/scripts/eval_compare.py" \
  "feat(redrob-rl): resumable scripts/eval_compare.py — fair before/after with 384-token budget"

commit_one "$ROOT/scripts/push_model_card.py" \
  "feat(redrob-rl): scripts/push_model_card.py — production HF model card with metrics tables"

commit_one "$ROOT/scripts/commit_and_push.sh" \
  "chore(redrob-rl): commit_and_push.sh helper"

commit_one "$ROOT/README.md" \
  "docs(redrob-rl): document the SFT→GRPO pipeline and embed plots/metrics"

commit_one "$ROOT/outputs/eval_metrics.json" \
  "metrics(redrob-rl): outputs/eval_metrics.json from the SFT+GRPO run"

commit_one "$ROOT/outputs/model_card.md" \
  "docs(redrob-rl): outputs/model_card.md rendered for HF Hub"

commit_one "$ROOT/data/processed/train.jsonl" \
  "data(redrob-rl): refreshed train.jsonl from DatasetBuilder"

commit_one "$ROOT/plots/training_curves.png" \
  "viz(redrob-rl): training_curves.png — reward (left axis, [0,1]) + GRPO loss (right axis) vs step"

commit_one "$ROOT/plots/baseline_vs_trained.png" \
  "viz(redrob-rl): baseline_vs_trained.png — per-episode reward, same eval rollout"

commit_one "$ROOT/plots/reward_components.png" \
  "viz(redrob-rl): reward_components.png — mean reward per component (rule-based)"

commit_one "$ROOT/plots/reward_distribution.png" \
  "viz(redrob-rl): reward_distribution.png — histogram of eval rewards"

git push origin main
echo "🎉 pushed to origin/main"
