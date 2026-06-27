/**
 * Multi-file résumé uploader.
 *
 * Drops one or many résumés (.pdf, .docx, .txt, .md) onto the page and
 * parses them server-side into Redrob-schema-conformant candidate records.
 *
 * The resulting JSON is offered as:
 *   1. an in-browser download (so the user can inspect / feed it to /api/rank);
 *   2. a synthetic `File` returned via `onParsed` so the parent can wire the
 *      records straight into the ranker without an extra click.
 */

import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { postParseResumes } from "../api";
import type { ParseResumesResponse } from "../types";

interface Props {
  onParsed?: (file: File, response: ParseResumesResponse) => void;
}

export const ResumeUpload: React.FC<Props> = ({ onParsed }) => {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<ParseResumesResponse | null>(null);

  const onDrop = useCallback(
    async (accepted: File[]) => {
      setError(null);
      setResponse(null);
      if (!accepted.length) return;
      setBusy(true);
      try {
        const res = await postParseResumes(accepted);
        setResponse(res);
        if (res.results.length) {
          const records = res.results.map((r) => r.record);
          const blob = new Blob([JSON.stringify(records, null, 2)], {
            type: "application/json",
          });
          const synthetic = new File(
            [blob],
            `resumes-parsed-${Date.now()}.json`,
            { type: "application/json" }
          );
          onParsed?.(synthetic, res);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [onParsed]
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    multiple: true,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/plain": [".txt"],
      "text/markdown": [".md"],
    },
    maxSize: 10 * 1024 * 1024,
  });

  function downloadJson() {
    if (!response?.results.length) return;
    const records = response.results.map((r) => r.record);
    const blob = new Blob([JSON.stringify(records, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "candidates-from-resumes.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="card-glow p-6 sm:p-8 transition-transform duration-500 hover:-translate-y-1">
      <header className="mb-5">
        <div className="text-[10px] uppercase tracking-widest text-bone-400">
          Resume parsing
        </div>
        <h2 className="text-lg sm:text-xl font-semibold text-bone-50 mt-1">
          Drop résumés — get schema-ready candidate records
        </h2>
        <p className="text-xs text-bone-400 mt-2 max-w-2xl">
          PDF · DOCX · TXT · MD. We extract name, headline, summary, career,
          education and skills using deterministic rule-based parsers (no LLM
          hallucinations) and validate every record against the official Redrob
          schema before handing it to the ranker.
        </p>
      </header>

      <div
        {...getRootProps()}
        className={`relative border-2 border-dashed rounded-md p-8 text-center transition-all cursor-pointer overflow-hidden ${
          isDragReject
            ? "border-red-400 bg-red-500/10"
            : isDragActive
            ? "border-bone-50 bg-bone-50/10 -translate-y-1"
            : "border-bone-400/40 hover:border-bone-50/70 hover:bg-bone-50/5"
        }`}
      >
        <input {...getInputProps()} />
        <div className="relative z-10">
          <svg
            className="mx-auto mb-3 opacity-80"
            width="34"
            height="34"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path d="M12 3v12m0 0l-4-4m4 4l4-4M5 21h14" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <p className="text-sm text-bone-200">
            {isDragActive
              ? "Drop them — we'll parse instantly"
              : "Drag résumés here, or click to browse"}
          </p>
          <p className="text-[11px] text-bone-400 mt-1 font-mono">
            up to 10 MB each · multiple files welcome
          </p>
        </div>
        {busy && (
          <div className="absolute inset-0 bg-ink-950/70 flex items-center justify-center backdrop-blur-sm">
            <span className="inline-flex items-center gap-2 text-xs uppercase tracking-widest text-bone-100">
              <span className="w-3 h-3 border-2 border-bone-50 border-t-transparent rounded-full animate-spin" />
              parsing…
            </span>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-4 text-xs text-red-300 border border-red-500/40 bg-red-500/10 px-3 py-2 rounded">
          {error}
        </div>
      )}

      <AnimatePresence>
        {response && (
          <motion.div
            key="report"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className="mt-5 space-y-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-mono text-bone-300">
                Parsed{" "}
                <span className="text-bone-50">{response.n_parsed}</span> of{" "}
                {response.n_uploaded} · {response.n_failed} failed
              </p>
              <button onClick={downloadJson} className="btn-ghost text-xs">
                Download .json
              </button>
            </div>
            <ul className="space-y-1.5 max-h-72 overflow-auto custom-scroll">
              {response.results.map((r, i) => {
                const rec = r.record as Record<string, unknown>;
                const profile = (rec.profile as Record<string, unknown>) || {};
                return (
                  <li
                    key={i}
                    className="card px-3 py-2 text-xs flex flex-wrap items-center justify-between gap-2"
                  >
                    <div className="min-w-0">
                      <div className="font-mono text-bone-200 truncate">
                        {r.filename || "(unnamed)"} · {String(rec.candidate_id)}
                      </div>
                      <div className="text-bone-400 text-[11px] truncate">
                        {String(profile.anonymized_name || "Anonymous")} ·{" "}
                        {String(profile.current_title || "")} ·{" "}
                        {String(profile.years_of_experience ?? 0)} yrs
                      </div>
                    </div>
                    <span
                      className={`pill border ${
                        r.schema_ok
                          ? "border-emerald-400/40 text-emerald-200 bg-emerald-500/10"
                          : "border-amber-400/40 text-amber-200 bg-amber-500/10"
                      }`}
                    >
                      {r.schema_ok
                        ? "schema ✓"
                        : `${r.schema_errors.length} schema issues`}
                    </span>
                  </li>
                );
              })}
              {response.errors.map((e, i) => (
                <li
                  key={`err-${i}`}
                  className="card px-3 py-2 text-xs border-red-400/40 bg-red-500/10"
                >
                  <div className="font-mono text-red-200 truncate">{e.filename}</div>
                  <div className="text-red-300 text-[11px]">{e.error}</div>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
};

export default ResumeUpload;
