#!/usr/bin/env bash
# scripts/push_hf_space.sh
# ──────────────────────────────────────────────────────────────────────────────
# Mirror the current repo to a HuggingFace Space, prepending the YAML metadata
# header HF requires at the top of the Space README.
#
# Usage:   scripts/push_hf_space.sh <hf-username>/<space-name>
# Example: scripts/push_hf_space.sh williyam/talentry-ai
#
# Requires: `huggingface-cli login` already done, or HF_TOKEN env var set.
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ID="${1:?usage: push_hf_space.sh <user>/<space>}"
HF_URL="https://huggingface.co/spaces/${REPO_ID}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TMP="$(mktemp -d -t talentry-hf.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

echo "→ Mirroring $ROOT to $TMP"
# Use `git ls-files` to copy only tracked files (skips .venv, node_modules, dist…)
git ls-files | rsync -a --files-from=- "$ROOT/" "$TMP/"

echo "→ Prepending HF Space YAML header to README.md"
cat "$ROOT/.hf_space_header.md" "$ROOT/README.md" > "$TMP/README.md"

cd "$TMP"
git init -q -b main
git remote add origin "$HF_URL"
git lfs install --skip-repo 2>/dev/null || true

# If the space already exists, fetch its current HEAD so our push is fast-forward.
if git ls-remote --exit-code "$HF_URL" main >/dev/null 2>&1; then
  echo "→ Space exists, fetching current main"
  git fetch -q origin main
  git reset -q --soft FETCH_HEAD
fi

git add -A
if [[ -n "$(git status --porcelain)" ]]; then
  git -c user.email="williyam64@gmail.com" -c user.name="Williyam M" \
    commit -q -m "deploy: sync from talentry-ai @ $(git -C "$ROOT" rev-parse --short HEAD)"
fi

echo "→ Pushing to $HF_URL (main)"
if [[ -n "${HF_TOKEN:-}" ]]; then
  # Auth via token (CI-friendly).
  git push -q "https://williyam:${HF_TOKEN}@huggingface.co/spaces/${REPO_ID}" HEAD:main
else
  git push -q origin HEAD:main
fi

echo "✅ Pushed. Open: $HF_URL"
