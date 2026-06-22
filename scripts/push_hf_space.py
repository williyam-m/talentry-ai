"""scripts/push_hf_space.py — sync the repo to a HuggingFace Space.

Uses the modern `hf` CLI (already installed as part of huggingface_hub) to:

  1. Create the Space (idempotent) with the right Docker SDK.
  2. Stage the repo into a temp directory containing **only** tracked files.
  3. Prepend the YAML metadata header HuggingFace requires at the top of the
     Space README.
  4. Upload the whole directory as a single commit.

Usage:
    python scripts/push_hf_space.py williyam/talentry-ai
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, text=True, **kw)


def main(repo_id: str) -> int:
    if "/" not in repo_id:
        sys.exit("repo id must be <user>/<space>")

    print(f"→ Target: https://huggingface.co/spaces/{repo_id}")

    # 1. Create the Space (idempotent — `--exist-ok` makes re-runs a no-op).
    create_cmd = [
        "hf",
        "repos",
        "create",
        repo_id,
        "--repo-type",
        "space",
        "--space-sdk",
        "docker",
        "--public",
        "--exist-ok",
    ]
    if tok := os.getenv("HF_TOKEN"):
        create_cmd += ["--token", tok]
    try:
        run(create_cmd)
    except subprocess.CalledProcessError as e:
        print(f"(repo create returned {e.returncode} — continuing to upload)")

    # 2. Stage tracked files into a temp dir.
    with tempfile.TemporaryDirectory(prefix="talentry-hf-") as tmp:
        tmp_path = Path(tmp)
        tracked = subprocess.check_output(
            ["git", "ls-files"], cwd=ROOT, text=True
        ).splitlines()
        print(f"→ Staging {len(tracked)} files into {tmp_path}")
        for rel in tracked:
            src = ROOT / rel
            dst = tmp_path / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        # 3. Prepend YAML header to README.md.
        header = (ROOT / ".hf_space_header.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        (tmp_path / "README.md").write_text(header + readme, encoding="utf-8")

        # 4. Upload.
        commit_msg = "deploy: sync from talentry-ai"
        try:
            sha = (
                subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT)
                .decode()
                .strip()
            )
            commit_msg += f" @ {sha}"
        except subprocess.CalledProcessError:
            pass

        cmd = [
            "hf",
            "upload",
            repo_id,
            str(tmp_path),
            ".",
            "--repo-type",
            "space",
            "--commit-message",
            commit_msg,
        ]
        if tok := os.getenv("HF_TOKEN"):
            cmd += ["--token", tok]
        run(cmd)

    print(f"\n✅ Done. Open: https://huggingface.co/spaces/{repo_id}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/push_hf_space.py <user>/<space>")
    sys.exit(main(sys.argv[1]))
