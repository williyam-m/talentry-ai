/** Talentry API client.
 *
 * All network calls go through this module so we can:
 *   • centralise base-URL configuration (Vite proxy in dev, same-origin in
 *     production behind the FastAPI static mount);
 *   • parse `application/json` *and* the FastAPI `{detail: ...}` error shape;
 *   • surface schema-validation failures (HTTP 422 from /api/rank) as a
 *     structured object - the UI uses this to render a git diff style
 *     report instead of a generic "request failed" toast.

 */

import type {
  ParseResumesResponse,
  RankErrorResponse,
  RankResponse,
  ValidateResponse,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

const DEFAULT_TIMEOUT_MS = 60_000;

// ── Internal helpers ───────────────────────────────────────────────────────

async function _fetch(
  url: string,
  init: RequestInit & { timeoutMs?: number } = {}
): Promise<Response> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...rest } = init;
  const ctrl = new AbortController();
  const timer = window.setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    return await fetch(url, { ...rest, signal: ctrl.signal });
  } finally {
    window.clearTimeout(timer);
  }
}

export class ApiError extends Error {
  status: number;
  body?: unknown;
  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/** Parse a possibly-JSON error body and throw a typed ApiError. */
async function _raise(res: Response): Promise<never> {
  let body: unknown;
  const ct = res.headers.get("content-type") || "";
  try {
    body = ct.includes("application/json") ? await res.json() : await res.text();
  } catch {
    body = undefined;
  }
  // FastAPI default: { detail: "..." }
  let message = res.statusText || `HTTP ${res.status}`;
  if (body && typeof body === "object") {
    const obj = body as Record<string, unknown>;
    if (typeof obj.detail === "string") message = obj.detail;
    else if (typeof obj.message === "string") message = obj.message as string;
  } else if (typeof body === "string" && body) {
    message = body;
  }
  throw new ApiError(message, res.status, body);
}

// ── Public endpoints ───────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  version: string;
  max_upload_mb: number;
  cached_sessions: number;
  rank_cache_size: number;
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await _fetch(`${BASE}/api/health`);
  if (!res.ok) await _raise(res);
  return res.json();
}

export async function getSchema(): Promise<unknown> {
  const res = await _fetch(`${BASE}/api/schema`);
  if (!res.ok) await _raise(res);
  return res.json();
}

export async function getSampleCandidates(limit = 10): Promise<unknown[]> {
  const res = await _fetch(`${BASE}/api/sample?limit=${limit}`);
  if (!res.ok) await _raise(res);
  return res.json();
}

export function sampleDownloadUrl(): string {
  return `${BASE}/api/sample/download`;
}

export interface RankOptions {
  candidates?: File | null;
  jd?: File | null;
  useSample?: boolean;
  topK?: number;
  skipValidation?: boolean;
}

/** Returned by `postRank` when the backend rejected the upload for schema. */
export class SchemaValidationError extends ApiError {
  payload: RankErrorResponse;
  constructor(payload: RankErrorResponse) {
    super(payload.message || "Schema validation failed", 422, payload);
    this.name = "SchemaValidationError";
    this.payload = payload;
  }
}

export async function postRank(opts: RankOptions): Promise<RankResponse> {
  const fd = new FormData();
  if (opts.candidates) fd.append("candidates", opts.candidates);
  if (opts.jd) fd.append("jd", opts.jd);

  const params = new URLSearchParams();
  if (opts.useSample) params.set("use_sample", "true");
  if (opts.topK) params.set("top_k", String(opts.topK));
  if (opts.skipValidation) params.set("skip_validation", "true");

  const url = `${BASE}/api/rank${params.toString() ? `?${params}` : ""}`;
  const res = await _fetch(url, {
    method: "POST",
    body: fd,
    timeoutMs: 15 * 60_000, // ranking the full 100k pool can take ~90 s

  });
  if (res.status === 422) {
    const body = (await res.json().catch(() => null)) as RankErrorResponse | null;
    if (body && body.error === "schema_validation_failed") {
      throw new SchemaValidationError(body);
    }
    throw new ApiError(body?.message || "Validation failed", 422, body);
  }
  if (!res.ok) await _raise(res);
  return res.json();
}

export async function postValidate(opts: {
  candidates?: File | null;
  useSample?: boolean;
}): Promise<ValidateResponse> {
  const fd = new FormData();
  if (opts.candidates) fd.append("candidates", opts.candidates);
  const params = new URLSearchParams();
  if (opts.useSample) params.set("use_sample", "true");
  const url = `${BASE}/api/validate${params.toString() ? `?${params}` : ""}`;
  const res = await _fetch(url, { method: "POST", body: fd });
  if (!res.ok) await _raise(res);
  return res.json();
}

export async function postParseResumes(files: File[]): Promise<ParseResumesResponse> {
  if (!files.length) throw new ApiError("no resume files supplied", 400);
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  const res = await _fetch(`${BASE}/api/parse-resumes`, {
    method: "POST",
    body: fd,
    timeoutMs: 2 * 60_000,
  });
  if (!res.ok) await _raise(res);
  return res.json();
}

export function csvDownloadUrl(session: string): string {
  return `${BASE}/api/submission.csv?session=${encodeURIComponent(session)}`;
}
