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

Production-grade hardening applied here:

* **Compression** via :class:`GZipMiddleware` so the ranker JSON (which can
  be hundreds of KB of breakdowns) ships ~5× smaller over the wire.
* **Hardened upload limits** (10 MB body cap for résumés/JSON uploads) to
  protect the Space from accidental OOM on free-tier 2 GB containers.
* **Schema-aware error responses** so the UI can render a GitHub-style
  green/red diff when an upload doesn't match the official Redrob schema.
* **Structured logging** + request-id propagation for observability.
* **In-memory LRU result cache** keyed by upload hash so re-clicking
  "Rank" on the same dataset returns in <10 ms.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import tempfile
import time
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any

import orjson
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from talentry import __version__
from talentry.io.candidates import iter_candidate_records, to_candidate
from talentry.io.resume import ResumeParseError, parse_resume
from talentry.io.schema import (
    diff_against_schema,
    load_schema,
    validate_batch,
    validate_candidate,
)
from talentry.io.submission import write_submission
from talentry.ranker import parse_job_description, rank_candidates

# ─────────────────────────────────────────────────────────────────────────────
# Configuration

# Maximum upload size (10 MB). The sample fixture is ~250 KB, real shards are
# JSONL-gz so they stay small; we don't expect legitimate uploads above this.
_MAX_UPLOAD_BYTES = int(os.getenv("TALENTRY_MAX_UPLOAD_MB", "10")) * 1024 * 1024
_RANK_CACHE_SIZE = 16  # tiny LRU; rank payloads are big

_LOG = logging.getLogger("talentry.api")
if not _LOG.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s rid=%(request_id)s %(name)s · %(message)s",
        defaults={"request_id": "-"},
    ))
    _LOG.addHandler(_h)
    _LOG.setLevel(os.getenv("TALENTRY_LOG_LEVEL", "INFO"))


app = FastAPI(
    title="Talentry AI",
    version=__version__,
    description=(
        "Production-grade candidate-ranking API powering the Talentry HuggingFace "
        "Space and CLI submissions for the Redrob × Hack2Skill India Runs hackathon."
    ),
)

# ─────────────────────────────────────────────────────────────────────────────
# Middleware

# gzip ≥ 500 B payloads — JSON breakdowns compress ~5×.
app.add_middleware(GZipMiddleware, minimum_size=500)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-request-id", "x-elapsed-ms"],
)


@app.middleware("http")
async def _observability(request: Request, call_next):
    """Inject a request-id, log timing, and set perf headers."""
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.request_id = rid
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except HTTPException:
        raise
    except Exception:  # pragma: no cover - last-resort 500
        _LOG.exception("unhandled error", extra={"request_id": rid})
        return JSONResponse(
            status_code=500,
            content={"error": "internal_server_error", "request_id": rid},
        )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    response.headers["x-request-id"] = rid
    response.headers["x-elapsed-ms"] = f"{elapsed_ms:.1f}"
    _LOG.info(
        "%s %s → %d (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        extra={"request_id": rid},
    )
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Fixture + state

_SAMPLE_FIXTURE = Path(__file__).resolve().parents[3] / "data" / "raw" / "sample_candidates.json"
_SESSIONS: dict[str, Path] = {}
_RANK_CACHE: "OrderedDict[str, bytes]" = OrderedDict()


def _cache_get(key: str) -> bytes | None:
    payload = _RANK_CACHE.get(key)
    if payload is not None:
        _RANK_CACHE.move_to_end(key)
    return payload


def _cache_put(key: str, payload: bytes) -> None:
    _RANK_CACHE[key] = payload
    _RANK_CACHE.move_to_end(key)
    while len(_RANK_CACHE) > _RANK_CACHE_SIZE:
        _RANK_CACHE.popitem(last=False)


def _max_top_k(n_candidates: int) -> int:
    return min(100, n_candidates)


# ─────────────────────────────────────────────────────────────────────────────
# Health + meta endpoints


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": __version__,
        "max_upload_mb": _MAX_UPLOAD_BYTES // (1024 * 1024),
        "cached_sessions": len(_SESSIONS),
        "rank_cache_size": len(_RANK_CACHE),
    }


@app.get("/api/schema")
def schema() -> JSONResponse:
    """Return the bundled candidate JSON-Schema (for the UI's docs panel)."""
    return JSONResponse(load_schema())


@app.get("/api/sample")
def sample(limit: int = Query(10, ge=1, le=100)) -> JSONResponse:
    """Return up to `limit` candidates from the bundled fixture."""
    if not _SAMPLE_FIXTURE.exists():
        raise HTTPException(404, "sample fixture not bundled in this deployment")
    out: list[dict[str, Any]] = []
    try:
        for i, rec in enumerate(iter_candidate_records(_SAMPLE_FIXTURE)):
            if i >= limit:
                break
            out.append(rec)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(500, f"could not read sample fixture: {exc}") from exc
    return JSONResponse(out)


@app.get("/api/sample/download")
def sample_download() -> FileResponse:
    """Stream the bundled sample_candidates.json as a downloadable file."""
    if not _SAMPLE_FIXTURE.exists():
        raise HTTPException(404, "sample fixture not bundled")
    return FileResponse(
        _SAMPLE_FIXTURE,
        media_type="application/json",
        filename="sample_candidates.json",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers


async def _read_capped(upload: UploadFile) -> bytes:
    """Read an upload, rejecting anything above the size cap."""
    payload = await upload.read()
    if len(payload) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            413,
            f"upload too large: {len(payload):,} bytes (limit {_MAX_UPLOAD_BYTES:,} bytes)",
        )
    return payload


def _load_records_from_bytes(payload: bytes, filename: str) -> list[dict[str, Any]]:
    """Persist the upload to a temp file then use our streaming loader."""
    suffix = Path(filename or "").suffix or ".jsonl"
    if suffix not in {".json", ".jsonl", ".gz"}:
        raise HTTPException(
            415,
            f"unsupported candidate file extension {suffix!r}; "
            "use .json, .jsonl, or .jsonl.gz",
        )
    with tempfile.NamedTemporaryFile("wb", delete=False, suffix=suffix) as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)
    try:
        try:
            return list(iter_candidate_records(tmp_path))
        except orjson.JSONDecodeError as exc:
            raise HTTPException(422, f"invalid JSON in upload: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(422, f"could not parse upload: {exc}") from exc
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Schema validation endpoints


@app.post("/api/validate")
async def validate(
    candidates: UploadFile | None = File(default=None),
    use_sample: bool = Query(False),
) -> JSONResponse:
    """Validate an uploaded candidates file against the official schema.

    Returns a structured report — including a GitHub-style diff for the
    first invalid record — so the UI can highlight exactly which fields
    are missing, wrong-typed, or violate enums/ranges.
    """
    if use_sample:
        if not _SAMPLE_FIXTURE.exists():
            raise HTTPException(404, "sample fixture not bundled")
        records = list(iter_candidate_records(_SAMPLE_FIXTURE))
    else:
        if candidates is None:
            raise HTTPException(400, "supply a `candidates` upload or set use_sample=true")
        payload = await _read_capped(candidates)
        if not payload:
            raise HTTPException(400, "upload was empty")
        records = _load_records_from_bytes(payload, candidates.filename or "")

    if not records:
        raise HTTPException(422, "no candidate records found in upload")

    report = validate_batch(records)
    body: dict[str, Any] = {"report": report.as_dict()}
    if report.n_invalid > 0 and report.first_invalid_index is not None:
        body["diff"] = diff_against_schema(records[report.first_invalid_index])
    return Response(content=orjson.dumps(body), media_type="application/json")


# ─────────────────────────────────────────────────────────────────────────────
# Resume parsing endpoint


@app.post("/api/parse-resumes")
async def parse_resumes_endpoint(
    files: list[UploadFile] = File(...),
) -> JSONResponse:
    """Parse one or more résumés into schema-conformant candidate records.

    Accepted formats: ``.pdf``, ``.docx``, ``.txt``, ``.md``.

    Successfully parsed records are *also* re-validated against the
    official schema so the UI knows immediately whether they can be
    fed straight into ``/api/rank``.
    """
    if not files:
        raise HTTPException(400, "supply at least one résumé file under `files`")

    parsed: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for idx, upload in enumerate(files):
        payload = await _read_capped(upload)
        if not payload:
            errors.append({"filename": upload.filename or "", "error": "empty file"})
            continue
        try:
            # Resume parsing is CPU-bound; run in a worker thread so the
            # event loop stays responsive when many uploads arrive at once.
            rec = await asyncio.to_thread(
                parse_resume,
                upload.filename or f"resume_{idx}.txt",
                payload,
                candidate_id=f"CAND_{idx + 1:07d}",
            )
            schema_errs = validate_candidate(rec)
            parsed.append({
                "record": rec,
                "schema_errors": [e.as_dict() for e in schema_errs],
                "schema_ok": not schema_errs,
                "filename": upload.filename,
            })
        except ResumeParseError as exc:
            errors.append({"filename": upload.filename or "", "error": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive
            _LOG.exception("resume parse failure")
            errors.append({
                "filename": upload.filename or "",
                "error": f"unexpected error: {exc.__class__.__name__}",
            })

    return JSONResponse({
        "n_uploaded": len(files),
        "n_parsed": len(parsed),
        "n_failed": len(errors),
        "results": parsed,
        "errors": errors,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Ranking endpoint (main feature)


@app.post("/api/rank")
async def rank(
    request: Request,
    candidates: UploadFile | None = File(default=None),
    jd: UploadFile | None = File(default=None),
    use_sample: bool = Query(False),
    top_k: int = Query(10, ge=1, le=100),
    skip_validation: bool = Query(False),
) -> Response:
    """Rank candidates and return JSON with full score breakdowns + CSV session.

    The request can supply candidates via:
      * ``candidates`` multipart upload (.json/.jsonl/.jsonl.gz), OR
      * ``use_sample=true`` to use the bundled fixture.

    By default we validate the upload against the official schema and
    refuse to rank obviously malformed inputs (with a structured diff in
    the response body). Pass ``skip_validation=true`` to override.
    """
    rid = getattr(request.state, "request_id", "-")

    if use_sample:
        if not _SAMPLE_FIXTURE.exists():
            raise HTTPException(404, "sample fixture not bundled")
        raw_records = list(iter_candidate_records(_SAMPLE_FIXTURE))
        cache_key = f"sample:{top_k}"
    else:
        if candidates is None:
            raise HTTPException(400, "supply a `candidates` upload or set use_sample=true")
        payload = await _read_capped(candidates)
        if not payload:
            raise HTTPException(400, "candidates upload was empty")
        raw_records = _load_records_from_bytes(payload, candidates.filename or "")
        digest = hashlib.sha1(payload, usedforsecurity=False).hexdigest()[:16]
        cache_key = f"u:{digest}:{top_k}"

    if not raw_records:
        raise HTTPException(422, "no candidate records found in upload")

    # ── Schema gate ──────────────────────────────────────────────────────
    if not skip_validation:
        report = validate_batch(raw_records, max_rows_reported=10)
        if report.n_invalid > 0:
            diff = (
                diff_against_schema(raw_records[report.first_invalid_index])
                if report.first_invalid_index is not None
                else None
            )
            _LOG.warning(
                "rejecting upload: %d/%d records failed schema validation",
                report.n_invalid,
                report.n_total,
                extra={"request_id": rid},
            )
            return JSONResponse(
                status_code=422,
                content={
                    "error": "schema_validation_failed",
                    "message": (
                        f"{report.n_invalid} of {report.n_total} records do not match "
                        "the official candidate schema. Fix the highlighted fields or "
                        "re-submit with skip_validation=true."
                    ),
                    "report": report.as_dict(),
                    "diff": diff,
                },
            )

    # ── Cache hit short-circuit ─────────────────────────────────────────
    cached = _cache_get(cache_key)
    if cached is not None:
        _LOG.info("rank cache hit %s", cache_key, extra={"request_id": rid})
        return Response(content=cached, media_type="application/json", headers={"x-cache": "hit"})

    parsed = [to_candidate(r) for r in raw_records]

    jd_text: str | None = None
    if jd is not None:
        jd_bytes = await _read_capped(jd)
        if jd_bytes:
            jd_text = jd_bytes.decode("utf-8", errors="replace")
    job = parse_job_description(jd_text)

    effective_top_k = min(top_k, _max_top_k(len(parsed)))

    # Ranking is CPU-bound — offload to a worker thread so the FastAPI
    # event loop continues serving other clients (health checks, etc.).
    ranked = await asyncio.to_thread(rank_candidates, parsed, job, effective_top_k)

    # Materialise CSV for the session (UI can offer a "download CSV" button
    # using GET /api/submission.csv) regardless of top_k size.
    session_id: str | None = None
    if ranked:
        session_id = os.urandom(8).hex()
        tmp = Path(tempfile.gettempdir()) / f"talentry-{session_id}.csv"
        try:
            write_submission(ranked, tmp)
        except Exception:
            import csv as _csv
            with tmp.open("w", newline="", encoding="utf-8") as fh:
                w = _csv.writer(fh)
                w.writerow(["rank", "candidate_id", "score", "reasoning"])
                for r in ranked:
                    w.writerow([r.rank, r.candidate_id, f"{r.score:.6f}", r.reasoning])
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
    body = orjson.dumps(payload)
    _cache_put(cache_key, body)
    return Response(content=body, media_type="application/json", headers={"x-cache": "miss"})


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
