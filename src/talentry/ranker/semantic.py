"""Hybrid lexical-semantic similarity between JD text and candidate text blobs.

We use TF-IDF + BM25 - *not* dense embeddings - because:

* The challenge caps us at ≤ 5 minutes CPU / no network for 100K candidates,
  so loading a 90 MB sentence-transformer + encoding 100K text blobs is right
  at the edge of the budget and adds a meaningful dependency risk to Stage 3
  reproduction.
* For a single JD vs many candidates, BM25 is essentially the strongest
  classical baseline and is *robust to short, noisy text* - exactly what
  career-history descriptions are.
* The combination of BM25 + a smaller TF-IDF cosine acts as a poor man's
  "hybrid retrieval" and captures both rare-term overlap and overall topical
  similarity.

We expose a single :class:`SemanticIndex` whose ``score`` returns a
[0, 1]-normalised value per candidate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer

from talentry.core.models import Candidate
from talentry.nlp.tokenize import tokenize


@dataclass
class SemanticIndex:
    bm25: BM25Okapi
    tfidf: TfidfVectorizer
    tfidf_matrix: any  # scipy.sparse
    candidate_ids: list[str]

    def score(self, jd_text: str) -> dict[str, float]:
        jd_tokens = tokenize(jd_text)
        bm25_scores = np.asarray(self.bm25.get_scores(jd_tokens), dtype=np.float32)

        # Min-max normalise BM25 to [0,1] (avoid division by zero).
        if bm25_scores.size:
            mn, mx = bm25_scores.min(), bm25_scores.max()
            bm25_norm = (bm25_scores - mn) / (mx - mn) if mx > mn else np.zeros_like(bm25_scores)
        else:
            bm25_norm = bm25_scores

        # TF-IDF cosine - JD vs all candidate blobs.
        jd_vec = self.tfidf.transform([" ".join(jd_tokens)])
        # cosine = (A . B) / (|A||B|); TfidfVectorizer rows are L2-normalised
        # already, so dot product == cosine.
        cos_scores = (self.tfidf_matrix @ jd_vec.T).toarray().ravel().astype(np.float32)
        if cos_scores.size:
            mn, mx = cos_scores.min(), cos_scores.max()
            cos_norm = (cos_scores - mn) / (mx - mn) if mx > mn else np.zeros_like(cos_scores)
        else:
            cos_norm = cos_scores

        # Hybrid: 60% BM25, 40% cosine. BM25 wins on rare-term overlap;
        # cosine smooths over phrasing differences.
        hybrid = 0.6 * bm25_norm + 0.4 * cos_norm
        return dict(zip(self.candidate_ids, hybrid.tolist(), strict=False))


def build_index(candidates: list[Candidate]) -> SemanticIndex:
    """Build the BM25 + TF-IDF index over the candidate text blobs.

    Assumes ``candidate.text_blob`` is already populated (see
    :func:`talentry.features.builder.build_text_blob`).
    """
    tokenised: list[list[str]] = [tokenize(c.text_blob) for c in candidates]
    bm25 = BM25Okapi(tokenised, k1=1.5, b=0.75)

    # TfidfVectorizer accepts pre-tokenised input via tokenizer=identity.
    tfidf = TfidfVectorizer(
        tokenizer=lambda s: s.split(),
        preprocessor=lambda s: s,
        token_pattern=None,  # silence the sklearn warning when tokenizer is set
        lowercase=False,
        min_df=2,
        max_df=0.85,
        sublinear_tf=True,
        norm="l2",
    )
    corpus_strs = [" ".join(t) for t in tokenised]
    tfidf_matrix = tfidf.fit_transform(corpus_strs)

    return SemanticIndex(
        bm25=bm25,
        tfidf=tfidf,
        tfidf_matrix=tfidf_matrix,
        candidate_ids=[c.candidate_id for c in candidates],
    )
