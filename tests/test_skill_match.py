from talentry.core.models import Candidate, Skill
from talentry.features.skill_match import score_skill_evidence


def _cand(skills):
    return Candidate(
        candidate_id="CAND_0000001",
        name="t", headline="", summary="", location="", country="",
        years_of_experience=5.0, current_title="x", current_company="y",
        current_company_size="51-200", current_industry="z",
        skills=skills,
    )


def test_keyword_stuffer_is_detected():
    # Six "expert" AI claims with zero evidence — classic stuffer.
    stuffer = _cand([
        Skill(name="LangChain", proficiency="expert", endorsements=0, duration_months=1),
        Skill(name="Pinecone", proficiency="expert", endorsements=0, duration_months=2),
        Skill(name="RAG", proficiency="expert", endorsements=0, duration_months=1),
        Skill(name="Prompt Engineering", proficiency="expert", endorsements=0, duration_months=1),
        Skill(name="Fine-tuning LLMs", proficiency="expert", endorsements=0, duration_months=2),
        Skill(name="LoRA", proficiency="expert", endorsements=0, duration_months=1),
    ])
    ev = score_skill_evidence(stuffer, [])
    assert ev.keyword_stuff_ratio >= 0.5


def test_real_practitioner_scores_high_on_retrieval_cluster():
    cand = _cand([
        Skill(name="FAISS", proficiency="advanced", endorsements=40, duration_months=44),
        Skill(name="Elasticsearch", proficiency="advanced", endorsements=54, duration_months=44),
        Skill(name="Embeddings", proficiency="expert", endorsements=48, duration_months=60),
        Skill(name="Information Retrieval", proficiency="expert", endorsements=15, duration_months=84),
    ])
    ev = score_skill_evidence(cand, [])
    assert ev.cluster_scores["embeddings_retrieval"] >= 0.85
