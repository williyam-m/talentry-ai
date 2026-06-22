"""``talentry-rank`` — the one command that produces the submission CSV.

This is the entry point pinned in ``submission_metadata.yaml``'s
``reproduce_command`` field:

    python -m talentry.cli.rank --candidates ./candidates.jsonl --out ./submission.csv

The command is deliberately tiny — all the engineering lives in the package,
and this file just argparses, dispatches and reports.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from talentry import __version__
from talentry.io.candidates import load_candidates
from talentry.io.submission import write_submission
from talentry.ranker import parse_job_description, rank_candidates


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="talentry-rank",
        description="Rank the top 100 candidates from a Redrob JSONL pool against a JD.",
    )
    p.add_argument(
        "--candidates",
        required=True,
        type=Path,
        help="Path to candidates.jsonl (gzip ok).",
    )
    p.add_argument(
        "--jd",
        type=Path,
        default=None,
        help="Path to job description text file. Defaults to the bundled JD.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("submission.csv"),
        help="Output CSV path. Default: submission.csv",
    )
    p.add_argument(
        "--top-k",
        type=int,
        default=100,
        help="Number of candidates to keep. Default: 100 (hackathon requirement).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on candidates loaded (useful for smoke tests).",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-stage progress logging.",
    )
    p.add_argument("--version", action="version", version=f"talentry-ai {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(message)s",
        stream=sys.stderr,
    )

    log = logging.getLogger("talentry.cli")
    log.info("[talentry-rank] v%s", __version__)
    log.info("[talentry-rank] loading candidates from %s …", args.candidates)
    t0 = time.perf_counter()
    candidates = load_candidates(args.candidates, limit=args.limit)
    log.info(
        "[talentry-rank] loaded %d candidates in %.2fs", len(candidates), time.perf_counter() - t0
    )

    jd = parse_job_description(args.jd)
    log.info("[talentry-rank] JD parsed — title=%r seniority=%s", jd.title, jd.seniority)

    ranked = rank_candidates(candidates, jd, top_k=args.top_k, progress=not args.quiet)
    if len(ranked) < args.top_k:
        log.warning(
            "[talentry-rank] only %d candidates ranked (< top_k=%d). "
            "Submission requires exactly 100 rows.",
            len(ranked),
            args.top_k,
        )

    strict = args.top_k == 100
    out = write_submission(ranked, args.out, strict=strict)
    log.info(
        "[talentry-rank] wrote %s submission → %s",
        "strict-validated" if strict else f"non-strict (top_k={args.top_k})",
        out,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
