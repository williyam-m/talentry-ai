"""Domain lexicons: role families, skill clusters, geography, behaviour priors.

Everything here is *data*, not logic. We keep it in code (not YAML) because:

* every value is referenced by a hard-coded module elsewhere, and a typo in
  YAML would only surface at runtime;
* the lexicon is small enough that auditing it in a PR is trivial;
* it ships with the wheel - no I/O at startup time.

The lexicons were curated from:

* the official `job_description.docx` ("things you absolutely need",
  "do NOT want", "ideal candidate is roughly…");
* the `candidate_schema.json` enums and signal envelopes;
* spot-checks against `sample_candidates.json` to make sure the rules fire
  on the real distribution.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Role families
# --------------------------------------------------------------------------- #
# A role family is what we map every `current_title` / `career.title` into so
# we can compare a candidate's *actual* career arc to the JD's *intended* arc.
#
# The JD targets: "Senior AI Engineer - owns the ranking, retrieval and
# matching systems". Role families are ranked from most-aligned (3.0) to
# definite-disqualifier (-1.0).
ROLE_FAMILIES: dict[str, dict] = {
    "ml_engineer": {
        "score": 3.0,
        "keywords": [
            "machine learning engineer", "ml engineer", "applied ml", "applied scientist",
            "ai engineer", "research engineer", "ml scientist", "ai scientist",
            "machine learning scientist",
        ],
    },
    "search_ir_engineer": {
        "score": 3.0,
        "keywords": [
            "search engineer", "search scientist", "ranking engineer", "retrieval engineer",
            "information retrieval", "recommendation systems engineer", "recsys engineer",
            "personalisation engineer", "personalization engineer",
        ],
    },
    "nlp_engineer": {
        "score": 2.8,
        "keywords": ["nlp engineer", "nlp scientist", "language model engineer"],
    },
    "data_scientist": {
        "score": 1.7,
        "keywords": ["data scientist", "research scientist"],
    },
    "data_engineer": {
        "score": 1.4,
        "keywords": ["data engineer", "analytics engineer", "etl engineer"],
    },
    "backend_engineer": {
        "score": 1.1,
        "keywords": [
            "backend engineer", "software engineer", "senior software engineer",
            "staff engineer", "principal engineer", "platform engineer",
            ".net developer", "java developer", "python developer", "go developer",
            "rust developer", "spring developer",
        ],
    },
    "fullstack_engineer": {
        "score": 0.7,
        "keywords": ["full stack developer", "full-stack developer", "fullstack developer"],
    },
    "frontend_engineer": {
        "score": 0.3,
        "keywords": ["frontend engineer", "front-end engineer", "ui engineer"],
    },
    "devops_cloud_engineer": {
        "score": 0.4,
        "keywords": [
            "devops engineer", "sre", "site reliability engineer",
            "cloud engineer", "infrastructure engineer", "platform reliability",
        ],
    },
    "mobile_engineer": {
        "score": 0.2,
        "keywords": ["mobile developer", "android developer", "ios developer"],
    },
    "qa_engineer": {
        "score": 0.0,
        "keywords": ["qa engineer", "test engineer", "sdet", "quality engineer"],
    },
    "computer_vision_only": {
        # JD explicitly: "primary expertise is computer vision … without significant
        # NLP/IR exposure" → soft disqualifier.
        "score": 0.4,
        "keywords": ["computer vision engineer", "cv engineer", "vision scientist"],
    },
    "non_engineering": {
        "score": -1.0,
        "keywords": [
            "marketing manager", "sales executive", "operations manager",
            "hr manager", "accountant", "project manager", "business analyst",
            "content writer", "graphic designer", "customer support",
            "mechanical engineer", "civil engineer", "electrical engineer",
            "product manager",
        ],
    },
}

# Flat reverse-index: keyword -> (family, score). Lower-cased for matching.
ROLE_KEYWORD_INDEX: dict[str, tuple[str, float]] = {
    kw.lower(): (family, meta["score"])
    for family, meta in ROLE_FAMILIES.items()
    for kw in meta["keywords"]
}

# --------------------------------------------------------------------------- #
# Skill clusters
# --------------------------------------------------------------------------- #
# Skills closely tied to the JD's "things you absolutely need" section.
# Membership in a cluster is worth more than a raw token match because the
# *evidence* (endorsements + duration_months + assessment score) is what we
# trust - not the literal string.

SKILL_CLUSTERS: dict[str, list[str]] = {
    "embeddings_retrieval": [
        "embeddings", "sentence transformers", "sentence-transformers",
        "bge", "e5", "openai embeddings", "vector search", "vector database",
        "faiss", "pinecone", "weaviate", "qdrant", "milvus", "opensearch",
        "elasticsearch", "haystack", "bm25", "information retrieval",
        "semantic search", "hybrid search",
    ],
    "ranking_recsys": [
        "recommendation systems", "recsys", "learning to rank", "learning-to-rank",
        "ltr", "xgboost", "lightgbm", "ranking", "ndcg", "mrr",
        "feature engineering", "click-through rate", "ctr",
    ],
    "nlp_llm": [
        "nlp", "natural language processing", "transformers",
        "hugging face transformers", "huggingface", "llm", "llms",
        "prompt engineering", "rag", "fine-tuning llms", "fine-tuning",
        "lora", "qlora", "peft", "langchain", "llamaindex",
    ],
    "ml_core": [
        "machine learning", "deep learning", "scikit-learn", "sklearn",
        "pytorch", "tensorflow", "statistical modeling", "mlflow", "wandb",
        "weights & biases", "mlops", "kubeflow", "bentoml", "feature store",
    ],
    "python_engineering": [
        "python", "fastapi", "flask", "django", "rest apis", "microservices",
        "docker", "kubernetes", "ci/cd", "postgresql", "redis", "kafka",
    ],
    "data_engineering": [
        "spark", "pyspark", "airflow", "dbt", "snowflake", "bigquery",
        "databricks", "data pipelines", "etl",
    ],
    # Visible "AI keyword" surface that fools a keyword-only ranker. We keep
    # this so we can *detect* and down-weight stuffers, not so we can reward
    # them.
    "ai_keyword_surface": [
        "langchain", "pinecone", "rag", "prompt engineering",
        "fine-tuning llms", "lora", "weaviate", "qdrant",
    ],
}

# JD-derived disqualifier surface - pure CV / robotics specialists.
CV_ONLY_SKILLS: frozenset[str] = frozenset(
    {
        "opencv", "yolo", "image classification", "object detection",
        "image segmentation", "gans", "cnn",
    }
)

SPEECH_ONLY_SKILLS: frozenset[str] = frozenset(
    {"speech recognition", "tts", "asr", "wav2vec"}
)

# --------------------------------------------------------------------------- #
# Geography
# --------------------------------------------------------------------------- #
PREFERRED_LOCATIONS: frozenset[str] = frozenset(
    {"pune", "noida", "delhi", "gurgaon", "gurugram", "new delhi", "delhi ncr"}
)
TIER1_INDIA_LOCATIONS: frozenset[str] = frozenset(
    {
        "bangalore", "bengaluru", "hyderabad", "mumbai", "chennai",
        "pune", "noida", "gurgaon", "gurugram", "delhi", "new delhi",
    }
)
INDIA_COUNTRY_TOKENS: frozenset[str] = frozenset({"india"})

# --------------------------------------------------------------------------- #
# Consulting-firm penalty list (JD: "People who have only worked at consulting
# firms in their entire career.")
# --------------------------------------------------------------------------- #
CONSULTING_FIRMS: frozenset[str] = frozenset(
    {
        "tcs", "tata consultancy services",
        "infosys",
        "wipro",
        "accenture",
        "cognizant",
        "capgemini",
        "hcl", "hcl technologies",
        "tech mahindra",
        "mindtree",
    }
)

PRODUCT_COMPANY_HINTS: frozenset[str] = frozenset(
    {
        "swiggy", "zomato", "flipkart", "razorpay", "cred",
        "ola", "uber", "mad street den", "pied piper", "hooli",
        "stark industries", "wayne enterprises", "globex inc",
        "acme corp", "dunder mifflin", "initech",
    }
)

# --------------------------------------------------------------------------- #
# Honeypot detection thresholds (see redrob_signals_doc / submission_spec)
# --------------------------------------------------------------------------- #
HONEYPOT_RULES: dict[str, float] = {
    # If sum(career.duration_months) > years_of_experience * 12 + 24mo
    "career_overflow_months": 24.0,
    # If candidate claims `expert` / `advanced` on a skill with 0 endorsements
    # AND 0 months → suspicious.
    "expert_with_zero_evidence_count": 3,
    # If expected_salary.min > expected_salary.max (inverted band).
    "inverted_salary": True,
    # signup_date in the future vs last_active.
    "signup_after_last_active": True,
}

__all__ = [
    "ROLE_FAMILIES",
    "ROLE_KEYWORD_INDEX",
    "SKILL_CLUSTERS",
    "CV_ONLY_SKILLS",
    "SPEECH_ONLY_SKILLS",
    "PREFERRED_LOCATIONS",
    "TIER1_INDIA_LOCATIONS",
    "INDIA_COUNTRY_TOKENS",
    "CONSULTING_FIRMS",
    "PRODUCT_COMPANY_HINTS",
    "HONEYPOT_RULES",
]
