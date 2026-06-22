import React, { useState } from "react";
import { postRank } from "../api";
import type { RankResponse } from "../types";

interface Props {
  onResult: (r: RankResponse) => void;
  onError: (msg: string) => void;
}

export const RunPanel: React.FC<Props> = ({ onResult, onError }) => {
  const [candidates, setCandidates] = useState<File | null>(null);
  const [jd, setJd] = useState<File | null>(null);
  const [topK, setTopK] = useState<number>(10);
  const [busy, setBusy] = useState(false);

  async function run(useSample: boolean) {
    setBusy(true);
    try {
      const res = await postRank({
        candidates: useSample ? null : candidates,
        jd,
        useSample,
        topK,
      });
      onResult(res);
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card p-6">
      <h2 className="text-sm uppercase tracking-widest text-bone-300 mb-4">
        Run the ranker
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <FileField
          label="Candidates (.json / .jsonl / .jsonl.gz)"
          onChange={setCandidates}
          file={candidates}
          accept=".json,.jsonl,.gz"
        />
        <FileField
          label="Job description (.txt, optional)"
          onChange={setJd}
          file={jd}
          accept=".txt,.md"
        />
      </div>

      <div className="flex items-center gap-4 mb-6">
        <label className="text-xs uppercase tracking-widest text-bone-300">
          Top‑K
        </label>
        <input
          type="number"
          min={1}
          max={100}
          value={topK}
          onChange={(e) => setTopK(Number(e.target.value))}
          className="w-24 bg-ink-800 border hairline px-3 py-1.5 text-sm font-mono"
        />
        <span className="text-[11px] text-bone-400">
          Hackathon submission requires exactly <span className="text-bone-50">100</span>.
        </span>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          className="btn-primary disabled:opacity-50"
          disabled={busy || !candidates}
          onClick={() => run(false)}
        >
          {busy ? "Ranking…" : "Rank uploaded pool"}
        </button>
        <button className="btn-ghost disabled:opacity-50" disabled={busy} onClick={() => run(true)}>
          {busy ? "Ranking…" : "Use bundled sample (50)"}
        </button>
      </div>
    </section>
  );
};

const FileField: React.FC<{
  label: string;
  file: File | null;
  onChange: (f: File | null) => void;
  accept?: string;
}> = ({ label, file, onChange, accept }) => (
  <label className="block">
    <div className="text-[11px] uppercase tracking-widest text-bone-400 mb-2">{label}</div>
    <div className="card flex items-center justify-between px-4 py-3">
      <span className="font-mono text-xs truncate text-bone-200 max-w-[60%]">
        {file ? file.name : "no file"}
      </span>
      <input
        type="file"
        accept={accept}
        className="hidden"
        id={label}
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
      <label htmlFor={label} className="btn-ghost cursor-pointer">
        Browse
      </label>
    </div>
  </label>
);
