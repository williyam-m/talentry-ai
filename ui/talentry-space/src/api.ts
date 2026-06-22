/** Minimal API client for the Talentry FastAPI backend. */

import type { RankResponse } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

export interface RankOptions {
  candidates?: File | null;
  jd?: File | null;
  useSample?: boolean;
  topK?: number;
}

export async function postRank(opts: RankOptions): Promise<RankResponse> {
  const fd = new FormData();
  if (opts.candidates) fd.append("candidates", opts.candidates);
  if (opts.jd) fd.append("jd", opts.jd);

  const params = new URLSearchParams();
  if (opts.useSample) params.set("use_sample", "true");
  if (opts.topK) params.set("top_k", String(opts.topK));

  const url = `${BASE}/api/rank${params.toString() ? `?${params}` : ""}`;
  const res = await fetch(url, { method: "POST", body: fd });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Rank failed (${res.status}): ${detail || res.statusText}`);
  }
  return (await res.json()) as RankResponse;
}

export function csvDownloadUrl(session: string): string {
  return `${BASE}/api/submission.csv?session=${encodeURIComponent(session)}`;
}

export async function getHealth(): Promise<{ status: string; version: string }> {
  const res = await fetch(`${BASE}/api/health`);
  if (!res.ok) throw new Error(`health ${res.status}`);
  return res.json();
}
