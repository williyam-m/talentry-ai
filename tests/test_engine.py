from pathlib import Path

from talentry.io.candidates import load_candidates
from talentry.ranker import parse_job_description, rank_candidates


SAMPLE = Path(__file__).parent.parent / "data" / "raw" / "sample_candidates.json"


def test_pipeline_runs_on_sample_and_ranks_recsys_engineer_first():
    cands = load_candidates(SAMPLE)
    jd = parse_job_description(None)
    ranked = rank_candidates(cands, jd, top_k=5)
    assert len(ranked) == 5
    # Ela Singh - explicit Recommendation Systems Engineer at Swiggy - should
    # easily rank #1 against this JD on this sample.
    assert ranked[0].candidate_id == "CAND_0000031"
    assert ranked[0].score >= ranked[1].score


def test_scores_are_non_increasing():
    cands = load_candidates(SAMPLE)
    jd = parse_job_description(None)
    ranked = rank_candidates(cands, jd, top_k=20)
    scores = [r.score for r in ranked]
    assert scores == sorted(scores, reverse=True)
