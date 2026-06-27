"""End-to-end ranker - exposes a single :func:`rank_candidates` entry point."""

from talentry.ranker.jd_parser import parse_job_description
from talentry.ranker.engine import rank_candidates

__all__ = ["rank_candidates", "parse_job_description"]
