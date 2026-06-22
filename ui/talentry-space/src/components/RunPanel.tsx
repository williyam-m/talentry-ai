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

  async function run() {
    setBusy(true);
    try {
      const res = await postRank({
        candidates,
        jd,
        useSample: false,
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
    <section className="card-glow p-6 sm:p-8 transition-transform duration-500 hover:-translate-y-1">
      <h2 className="text-sm uppercase tracking-widest text-bone-300 mb-5 flex items-center gap-2">
        <span className="inline-block w-2 h-2 rounded-full bg-bone-50 animate-pulse" />
        Run the ranker
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
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

      <div className="flex flex-wrap items-center gap-4 mb-6">
        <label className="text-xs uppercase tracking-widest text-bone-300">
          Top‑K
        </label>
        <input
          type="number"
          min={1}
          max={100}
          value={topK}
          onChange={(e) => setTopK(Number(e.target.value))}
          className="w-24 bg-ink-800/80 border hairline px-3 py-1.5 text-sm font-mono focus:outline-none focus:border-bone-50 transition-colors"
        />
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          className="btn-primary disabled:opacity-50 group"
          disabled={busy || !candidates}
          onClick={run}
        >
          {busy ? (
            <>
              <Spinner /> Ranking…
            </>
          ) : (
            <>
              Rank uploaded pool
              <span className="transition-transform group-hover:translate-x-0.5">→</span>
            </>
          )}
        </button>
      </div>
    </section>
  );
};

const Spinner: React.FC = () => (
  <span className="inline-block w-3 h-3 border-2 border-ink-950 border-t-transparent rounded-full animate-spin" />
);

const FileField: React.FC<{
  label: string;
  file: File | null;
  onChange: (f: File | null) => void;
  accept?: string;
}> = ({ label, file, onChange, accept }) => (
  <label className="block">
    <div className="text-[11px] uppercase tracking-widest text-bone-400 mb-2">{label}</div>
    <div className="card flex items-center justify-between px-4 py-3 hover:border-bone-50/40 transition-colors">
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
