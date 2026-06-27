#!/usr/bin/env bash
# scripts/push_hf_space.sh
# ──────────────────────────────────────────────────────────────────────────────
# Mirror the current repo to a HuggingFace Space, prepending the YAML metadata
# header HF requires at the top of the Space README.
#
# Usage:   scripts/push_hf_space.sh <hf-username>/<space-name> [<hf-username>]
# Example: scripts/push_hf_space.sh williyam/talentry-ai
#          scripts/push_hf_space.sh williyam/talentry-ai myuser
#
# Auth:    Either `huggingface-cli login` first, OR set HF_TOKEN env var.
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ID="${1:?usage: push_hf_space.sh <user>/<space> [<hf-username>]}"
HF_USER="${2:-${REPO_ID%%/*}}"
HF_URL="https://huggingface.co/spaces/${REPO_ID}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Resolve an HF token from either env var or the CLI's cached login.
HF_TOKEN="${HF_TOKEN:-}"
if [[ -z "${HF_TOKEN}" ]]; then
  if command -v huggingface-cli >/dev/null 2>&1; then
    HF_TOKEN="$(huggingface-cli whoami --token 2>/dev/null || true)"
  fi
  if [[ -z "${HF_TOKEN}" && -f "${HOME}/.cache/huggingface/token" ]]; then
    HF_TOKEN="$(cat "${HOME}/.cache/huggingface/token")"
  fi
fi
if [[ -z "${HF_TOKEN}" ]]; then
  echo "⚠️  No HF_TOKEN found. Run 'huggingface-cli login' or export HF_TOKEN."
  exit 1
fi

TMP="$(mktemp -d -t talentry-hf.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

echo "→ Mirroring $ROOT to $TMP (tracked files only)"
git ls-files | rsync -a --files-from=- "$ROOT/" "$TMP/"

echo "→ Prepending HF Space YAML header to README.md"
cat "$ROOT/.hf_space_header.md" "$ROOT/README.md" > "$TMP/README.md"

cd "$TMP"
git init -q -b main
git remote add origin "$HF_URL"
git lfs install --skip-repo 2>/dev/null || true

PUSH_URL="https://${HF_USER}:${HF_TOKEN}@huggingface.co/spaces/${REPO_ID}"

if git ls-remote --exit-code "$PUSH_URL" main >/dev/null 2>&1; then
  echo "→ Space exists, fetching current main"
  git fetch -q "$PUSH_URL" main
  git reset -q --soft FETCH_HEAD
fi

git add -A
if [[ -n "$(git status --porcelain)" ]]; then
  git -c user.email="williyam64@gmail.com" -c user.name="Williyam M" \
    commit -q -m "deploy: sync from talentry-ai @ $(git -C "$ROOT" rev-parse --short HEAD)"
fi

echo "→ Pushing to $HF_URL (main)"
git push -q "$PUSH_URL" HEAD:main

echo "✅ Pushed. Open: $HF_URL"
