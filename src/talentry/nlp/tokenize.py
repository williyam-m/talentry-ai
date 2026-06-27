"""Tokenisation + lightweight text normalisation.

The Talentry ranker is built to satisfy the hackathon's *zero-network, ≤5 min,
CPU-only* budget over 100K candidates. That rules out heavyweight embedding
models. We therefore lean on a carefully-tuned BM25 + TF-IDF stack - but those
in turn live and die by tokenisation quality on the noisy career-history text.

This module centralises the rules so other components don't disagree.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache

# A small, domain-tuned stop-list. We keep it short on purpose - over-aggressive
# stop-listing makes BM25 score short profiles unfairly.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "the", "to", "of", "for", "in", "on", "at", "by",
        "with", "from", "as", "is", "are", "was", "were", "be", "been", "being",
        "this", "that", "these", "those", "it", "its", "i", "we", "you", "he",
        "she", "they", "them", "his", "her", "their", "our", "your", "my",
        "or", "but", "if", "then", "than", "so", "not", "no", "yes", "do",
        "does", "did", "have", "has", "had", "will", "would", "should", "could",
        "can", "may", "might", "also", "into", "out", "up", "down", "very",
        "more", "most", "less", "least", "some", "any", "all", "each", "other",
        "such", "about", "across", "between", "through", "while", "during",
    }
)

# Pre-compiled patterns
_NON_ALPHANUM = re.compile(r"[^a-z0-9+#./\-]+")
_MULTI_SPACE = re.compile(r"\s+")
_VERSION_NOISE = re.compile(r"\b\d{4}\b")  # strip year-numbers that explode IDF

# Domain synonyms - collapsed at tokenisation time so BM25 doesn't see
# "ai/ml/AI engineer/machine-learning" as four different terms.
_SYNONYMS: dict[str, str] = {
    "ai": "ai_ml",
    "ml": "ai_ml",
    "ml/ai": "ai_ml",
    "ai/ml": "ai_ml",
    "genai": "ai_ml",
    "gen-ai": "ai_ml",
    "llm": "llm",
    "llms": "llm",
    "rag": "rag",
    "ir": "information_retrieval",
    "info-retrieval": "information_retrieval",
    "info_retrieval": "information_retrieval",
    "nlp": "nlp",
    "natural-language-processing": "nlp",
    "ltr": "learning_to_rank",
    "learning-to-rank": "learning_to_rank",
    "vector-db": "vector_database",
    "vectordb": "vector_database",
    "vector-search": "vector_search",
    "embedding": "embeddings",
    "embeddings": "embeddings",
    "fine-tune": "fine_tuning",
    "fine-tuning": "fine_tuning",
    "finetune": "fine_tuning",
    "finetuning": "fine_tuning",
    "qlora": "peft",
    "lora": "peft",
    "peft": "peft",
    "sentence-transformer": "sentence_transformers",
    "sentence-transformers": "sentence_transformers",
    "huggingface": "hugging_face",
    "hugging-face": "hugging_face",
    "tcs": "consulting_firm",
    "infosys": "consulting_firm",
    "wipro": "consulting_firm",
    "accenture": "consulting_firm",
    "cognizant": "consulting_firm",
    "capgemini": "consulting_firm",
    "hcl": "consulting_firm",
    "tech-mahindra": "consulting_firm",
    "mindtree": "consulting_firm",
}


@lru_cache(maxsize=4096)
def _canonical(token: str) -> str:
    return _SYNONYMS.get(token, token)


def normalise(text: str) -> str:
    """Lower-case + strip noisy punctuation while keeping `c++`, `node.js`, etc."""
    if not text:
        return ""
    text = text.lower()
    text = _VERSION_NOISE.sub(" ", text)
    text = _NON_ALPHANUM.sub(" ", text)
    text = _MULTI_SPACE.sub(" ", text)
    return text.strip()


def tokenize(text: str, *, drop_stop: bool = True) -> list[str]:
    """Return a list of canonicalised tokens."""
    out: list[str] = []
    for raw in normalise(text).split():
        tok = _canonical(raw)
        if drop_stop and tok in _STOPWORDS:
            continue
        if len(tok) < 2:
            continue
        out.append(tok)
    return out


def tokens_set(text: str) -> frozenset[str]:
    return frozenset(tokenize(text))


def char_ngrams(text: str, n: int = 3) -> Iterable[str]:
    """Character n-grams for fuzzy skill matching ("postgresql" ↔ "postgres")."""
    text = normalise(text).replace(" ", "_")
    if len(text) < n:
        yield text
        return
    for i in range(len(text) - n + 1):
        yield text[i : i + n]
