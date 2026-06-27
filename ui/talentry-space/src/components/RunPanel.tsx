/**
 * Primary "Run the ranker" control panel.
 *
 * Three orthogonal ways to feed candidates to the API:
 *   1. Upload your own `.json/.jsonl/.jsonl.gz` (drag-and-drop).
 *   2. Click "Feed sample candidates" → uses the bundled fixture.
 *   3. Use the `prefilled` prop from the parent (e.g. résumé parser).
 *
 * Schema-validation errors are NOT caught here — they bubble up to
 * App.tsx so it can render the dedicated <SchemaDiff/> panel.
 */

import React, { useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { postRank, SchemaValidationError } from "../api";
import type { RankResponse } from "../types";

interface Props {
  onResult: (r: RankResponse) => void;
  onError: (msg: string) => void;
  onSchemaError: (err: SchemaValidationError) => void;
  prefilled?: File | null;
}

export const RunPanel: React.FC<Props> = ({
  onResult,
  onError,
  onSchemaError,
  prefilled,
}) => {
  const [candidates, setCandidates] = useState<File | null>(null);
  const [jd, setJd] = useState<File | null>(null);
  const [topK, setTopK] = useState<number>(10);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"upload" | "sample">("upload");

  useEffect(() => {
    if (prefilled) {
      setCandidates(prefilled);
      setMode("upload");
    }
  }, [prefilled]);

  async function runUpload() {
    if (!candidates) return;
    await runRequest({ candidates, jd, topK });
  }

  async function runSample() {
    setMode("sample");
    await runRequest({ useSample: true, jd, topK });
  }

  async function runRequest(opts: {
    candidates?: File | null;
    jd?: File | null;
    topK?: number;
    useSample?: boolean;
  }) {
    setBusy(true);
    try {
      const res = await postRank(opts);
      onResult(res);
    } catch (e) {
      if (e instanceof SchemaValidationError) {
        onSchemaError(e);
      } else {
        onError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(false);
    }
  }

  const candidateDrop = useDropzone({
    onDrop: (files) => files[0] && setCandidates(files[0]),
    multiple: false,
    accept: {
      "application/json": [".json", ".jsonl"],
      "application/gzip": [".gz"],
    },
    maxSize: 10 * 1024 * 1024,
  });

  const jdDrop = useDropzone({
    onDrop: (files) => files[0] && setJd(files[0]),
    multiple: false,
    accept: { "text/plain": [".txt", ".md"] },
    maxSize: 1 * 1024 * 1024,
  });

  return (
    <section className="card-glow p-6 sm:p-8 transition-transform duration-500 hover:-translate-y-1">
      <header className="mb-5">
        <h2 className="text-sm uppercase tracking-widest text-bone-300 flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-bone-50 animate-pulse" />
          Run the ranker
        </h2>
        <p className="text-xs text-bone-400 mt-2 max-w-2xl">
          Drop your candidates file, or click <em>"Feed sample candidates"</em> to
          explore with the bundled 50-row fixture. Every upload is validated
          against the official Redrob schema first — mismatches surface as a
          git diff style report, not a stack trace.
        </p>

      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
        <DropField
          label="Candidates (.json / .jsonl / .jsonl.gz)"
          dropzone={candidateDrop}
          file={candidates}
          onClear={() => setCandidates(null)}
          accent="bone"
        />
        <DropField
          label="Job description (.txt, optional)"
          dropzone={jdDrop}
          file={jd}
          onClear={() => setJd(null)}
          accent="bone"
        />
      </div>

      <div className="flex flex-wrap items-center gap-4 mb-6">
        <label className="text-xs uppercase tracking-widest text-bone-300">Top‑K</label>
        <input
          type="number"
          min={1}
          max={100}
          value={topK}
          onChange={(e) => setTopK(Math.min(100, Math.max(1, Number(e.target.value) || 1)))}
          className="w-24 bg-ink-800/80 border hairline px-3 py-1.5 text-sm font-mono focus:outline-none focus:border-bone-50 transition-colors"
        />
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          className="btn-primary disabled:opacity-50 group"
          disabled={busy || !candidates}
          onClick={runUpload}
        >
          {busy && mode === "upload" ? (
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

        <button
          className="btn-ghost relative overflow-hidden disabled:opacity-50 group"
          disabled={busy}
          onClick={runSample}
          title="Use the bundled 50-row sample to explore the UI"
        >
          {busy && mode === "sample" ? (
            <>
              <Spinner /> Ranking sample…
            </>
          ) : (
            <>
              <SparkleIcon /> Feed sample candidates
            </>
          )}
        </button>
      </div>

      <AnimatePresence>
        {candidates && (
          <motion.p
            key={candidates.name}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-4 text-[11px] text-bone-400 font-mono"
          >
            Ready: <span className="text-bone-200">{candidates.name}</span> (
            {(candidates.size / 1024).toFixed(1)} KB)
          </motion.p>
        )}
      </AnimatePresence>
    </section>
  );
};

// ───────────────────────── helpers ─────────────────────────────────────────

const Spinner: React.FC = () => (
  <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
);

const SparkleIcon: React.FC = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 3l1.7 4.6 4.6 1.7-4.6 1.7L12 15.6 10.3 11l-4.6-1.7 4.6-1.7L12 3z" />
    <path d="M19 14l1 2.6 2.6 1-2.6 1-1 2.6-1-2.6-2.6-1 2.6-1 1-2.6z" />
  </svg>
);

interface DropFieldProps {
  label: string;
  file: File | null;
  onClear: () => void;
  dropzone: ReturnType<typeof useDropzone>;
  accent: "bone" | "red";
}

const DropField: React.FC<DropFieldProps> = ({ label, file, onClear, dropzone }) => {
  const { getRootProps, getInputProps, isDragActive, isDragReject } = dropzone;
  return (
    <div>
      <div className="text-[11px] uppercase tracking-widest text-bone-400 mb-2">{label}</div>
      <div
        {...getRootProps()}
        className={`relative card flex items-center justify-between px-4 py-3 cursor-pointer transition-all ${
          isDragReject
            ? "border-red-400/60 bg-red-500/10"
            : isDragActive
            ? "border-bone-50/80 bg-bone-50/10 -translate-y-0.5"
            : "hover:border-bone-50/40"
        }`}
      >
        <input {...getInputProps()} />
        <span className="font-mono text-xs truncate text-bone-200 max-w-[60%]">
          {file ? file.name : isDragActive ? "drop to attach" : "drag or click to attach"}
        </span>
        {file ? (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onClear();
            }}
            className="btn-ghost text-[10px] px-2 py-1"
          >
            clear
          </button>
        ) : (
          <span className="btn-ghost pointer-events-none">Browse</span>
        )}
      </div>
    </div>
  );
};

export default RunPanel;
