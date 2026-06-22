"""FastAPI server — powers the HuggingFace Space sandbox + general HTTP demo.

The server is deliberately stateless. Each ``POST /api/rank`` invocation:

  1. Parses the optional JD text from the multipart body (falls back to
     the bundled Senior-AI-Engineer JD if absent).
  2. Loads the uploaded candidates file (`.json`, `.jsonl`, `.jsonl.gz`).
  3. Runs the full Talentry pipeline.
  4. Returns the ranked top-K plus the full :class:`ScoreBreakdown` JSON
     so the UI can render the explainability drill-down.

Why JSON-in / JSON-out? Because the HuggingFace Space sandbox spec requires
the system to "accept a small candidate sample (≤100 candidates) as input
… and produce a ranked CSV" — which we satisfy with the additional
``GET /api/submission.csv?session=<id>`` endpoint that serves a freshly
written, validator-clean CSV.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import orjson
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from talentry import __version__
from talentry.io.candidates import iter_candidate_records, to_candidate
from talentry.io.submission import write_submission
from talentry.ranker import parse_job_description, rank_candidates

_LOG = logging.getLogger("talentry.api")

app = FastAPI(
    title="Talentry AI",
    version=__version__,
    description=(
        "Production-grade candidate-ranking API powering the Talentry HuggingFace "
        "Space and CLI submissions for the Redrob × Hack2Skill India Runs hackathon."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to bundled sample fixture (when running inside the HF space the
# repo is laid out so this resolves to ./data/raw/sample_candidates.json).
_SAMPLE_FIXTURE = Path(__file__).resolve().parents[3] / "data" / "raw" / "sample_candidates.json"
_SESSIONS: dict[str, Path] = {}


def _max_top_k(n_candidates: int) -> int:
    return min(100, n_candidates)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/api/sample")
def sample(limit: int = Query(10, ge=1, le=100)) -> JSONResponse:
    """Return up to `limit` candidates from the bundled fixture."""
    if not _SAMPLE_FIXTURE.exists():
        raise HTTPException(404, "sample fixture not bundled in this deployment")
    out = []
    for i, rec in enumerate(iter_candidate_records(_SAMPLE_FIXTURE)):
        if i >= limit:
            break
        out.append(rec)
    return JSONResponse(out)


def _load_records_from_upload(payload: bytes, filename: str) -> list[dict[str, Any]]:
    """Persist the upload to a temp file then use our streaming loader."""
    suffix = Path(filename or "").suffix or ".jsonl"
    with tempfile.NamedTemporaryFile("wb", delete=False, suffix=suffix) as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)
    try:
        return list(iter_candidate_records(tmp_path))
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


@app.post("/api/rank")
async def rank(
    candidates: UploadFile | None = File(default=None),
    jd: UploadFile | None = File(default=None),
    use_sample: bool = Query(False),
    top_k: int = Query(10, ge=1, le=100),
) -> JSONResponse:
    """Rank candidates and return JSON with full score breakdowns + CSV session.

    The request can supply candidates via:
      * ``candidates`` multipart upload (.json/.jsonl/.jsonl.gz), OR
      * ``use_sample=true`` to use the bundled 50-row fixture.
    """
    if use_sample:
        if not _SAMPLE_FIXTURE.exists():
            raise HTTPException(404, "sample fixture not bundled")
        raw_records = list(iter_candidate_records(_SAMPLE_FIXTURE))
    else:
        if candidates is None:
            raise HTTPException(400, "supply a `candidates` upload or set use_sample=true")
        payload = await candidates.read()
        if not payload:
            raise HTTPException(400, "candidates upload was empty")
        raw_records = _load_records_from_upload(payload, candidates.filename or "")

    if not raw_records:
        raise HTTPException(422, "no candidate records found in upload")

    parsed = [to_candidate(r) for r in raw_records]

    jd_text: str | None = None
    if jd is not None:
        jd_bytes = await jd.read()
        if jd_bytes:
            jd_text = jd_bytes.decode("utf-8", errors="replace")
    job = parse_job_description(jd_text)

    effective_top_k = min(top_k, _max_top_k(len(parsed)))
    ranked = rank_candidates(parsed, job, top_k=effective_top_k)

    # Materialise CSV for the session (UI can offer a "download CSV" button
    # using GET /api/submission.csv). We only register a session when the
    # top_k is exactly 100, otherwise the writer (rightly) refuses.
    session_id: str | None = None
    if len(ranked) == 100:
        session_id = os.urandom(8).hex()
        tmp = Path(tempfile.gettempdir()) / f"talentry-{session_id}.csv"
        write_submission(ranked, tmp)
        _SESSIONS[session_id] = tmp

    payload = {
        "version": __version__,
        "jd": {
            "title": job.title,
            "seniority": job.seniority,
            "min_years": job.min_years,
            "max_years": job.max_years,
            "must_have_skills": job.must_have_skills,
            "preferred_locations": job.preferred_locations,
        },
        "n_candidates": len(parsed),
        "n_returned": len(ranked),
        "session_id": session_id,
        "results": [
            {
                "candidate_id": r.candidate_id,
                "rank": r.rank,
                "score": r.score,
                "reasoning": r.reasoning,
                "breakdown": r.breakdown.as_dict(),
            }
            for r in ranked
        ],
    }
    return Response(content=orjson.dumps(payload), media_type="application/json")


@app.get("/api/submission.csv")
def submission_csv(session: str = Query(...)) -> FileResponse:
    path = _SESSIONS.get(session)
    if path is None or not path.exists():
        raise HTTPException(404, "no submission found for that session id")
    return FileResponse(
        path,
        media_type="text/csv",
        filename="submission.csv",
    )


def run() -> None:  # pragma: no cover
    """uvicorn entry-point used by the ``talentry-serve`` script."""
    import uvicorn

    host = os.getenv("TALENTRY_HOST", "0.0.0.0")
    port = int(os.getenv("TALENTRY_PORT", "7860"))
    uvicorn.run("talentry.api.server:app", host=host, port=port, log_level="info")
