"""Tests for the rule-based resume parser."""

from __future__ import annotations

import pytest

from talentry.io.resume import ResumeParseError, parse_resume
from talentry.io.schema import validate_candidate

_SAMPLE = b"""Jane Doe
Senior AI Engineer at Acme

Summary
Experienced ML engineer with 8 years of experience in NLP and recommender
systems. Built recsys at scale using PyTorch, transformers, and FAISS.

Experience
Senior AI Engineer at Acme, 2020 - present
Led a team of 5 engineers to build a recommendation system using PyTorch,
FAISS, and Kubernetes.
Machine Learning Engineer, BigCo, 2017 - 2020
Built NLP pipelines using transformers, BERT, and HuggingFace.

Education
IIT Bombay, B.Tech Computer Science, 2013 - 2017

Skills
Python, PyTorch, TensorFlow, FAISS, Kubernetes, AWS, NLP, transformers
"""


def test_parse_txt_resume_produces_schema_valid_record() -> None:
    rec = parse_resume("jane.txt", _SAMPLE, candidate_id="CAND_0000001")
    assert rec["profile"]["anonymized_name"] == "Jane Doe"
    assert rec["profile"]["years_of_experience"] > 0
    assert len(rec["career_history"]) >= 1
    assert len(rec["skills"]) >= 3
    # Round-trip through the schema validator.
    errors = validate_candidate(rec)
    assert errors == [], f"resume parser must emit schema-valid records: {errors[:3]}"


def test_empty_upload_raises_parse_error() -> None:
    with pytest.raises(ResumeParseError):
        parse_resume("empty.txt", b"")


def test_unknown_format_raises_parse_error() -> None:
    with pytest.raises(ResumeParseError):
        parse_resume("file.xyz", b"hello world")
