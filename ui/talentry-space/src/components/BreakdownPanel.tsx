import React from "react";
import type { RankedRow } from "../types";

const labels: Record<string, string> = {
  title_alignment: "Title / career trajectory",
  semantic_fit: "Hybrid retrieval (BM25 + TF-IDF)",
  skill_evidence: "Evidence-weighted skill score",
  experience_band: "Years-of-experience band",
  location: "Location & relocation",
  behavioural: "Behavioural multiplier",
  honeypot_penalty: "Honeypot penalty",
};

export const BreakdownPanel: React.FC<{ row: RankedRow | null }> = ({ row }) => {
  if (!row) {
    return (
      <section className="card p-6 text-bone-400 text-sm">
        Select a candidate to see the score breakdown.
      </section>
    );
  }
  const b = row.breakdown;
  const items = [
    { key: "title_alignment", value: b.title_alignment, range: [-1, 1] as const },
    { key: "semantic_fit", value: b.semantic_fit, range: [0, 1] as const },
    { key: "skill_evidence", value: b.skill_evidence, range: [0, 1] as const },
    { key: "experience_band", value: b.experience_band, range: [0, 1] as const },
    { key: "location", value: b.location, range: [0, 1] as const },
    { key: "behavioural", value: b.behavioural, range: [0.55, 1.2] as const },
    { key: "honeypot_penalty", value: -b.honeypot_penalty, range: [-0.5, 0] as const },
  ];
  return (
    <section className="card p-6">
      <header className="mb-5 flex items-baseline justify-between">
        <div>
          <h2 className="text-sm uppercase tracking-widest text-bone-300">Score breakdown</h2>
          <div className="mt-1 text-xs text-bone-400 font-mono">{row.candidate_id} · rank {row.rank}</div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-widest text-bone-400">final</div>
          <div className="text-2xl font-mono">{b.final.toFixed(4)}</div>
        </div>
      </header>
      <div className="space-y-3">
        {items.map((i) => (
          <Bar key={i.key} label={labels[i.key]} value={i.value} range={i.range} />
        ))}
      </div>
      <p className="mt-6 text-xs text-bone-300 leading-relaxed">{row.reasoning}</p>
    </section>
  );
};

const Bar: React.FC<{ label: string; value: number; range: readonly [number, number] }> = ({ label, value, range }) => {
  const [lo, hi] = range;
  const norm = Math.max(0, Math.min(1, (value - lo) / (hi - lo)));
  return (
    <div>
      <div className="flex items-center justify-between text-[11px] tracking-wider uppercase">
        <span className="text-bone-300">{label}</span>
        <span className="font-mono text-bone-200">{value.toFixed(3)}</span>
      </div>
      <div className="h-1.5 bg-ink-800 mt-1.5 relative overflow-hidden">
        <div
          className="absolute top-0 left-0 h-full bg-bone-50"
          style={{ width: `${(norm * 100).toFixed(1)}%` }}
        />
      </div>
    </div>
  );
};
