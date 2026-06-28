/**
 * Git diff style report between an uploaded record and the official
 * Redrob `candidate_schema.json`.

 *
 * Visual contract:
 *   • `match`  → neutral grey line.
 *   • `missing` (schema requires it but upload lacks it) → red `-` line.
 *   • `extra`  (upload provided a field the schema doesn't declare) → green `+` line.
 *
 * The component is deliberately self-contained: it only depends on Tailwind
 * + our existing `diff` npm package for the side-by-side stringified record
 * diff, so it can be dropped into any error toast.
 */

import React, { useMemo, useState } from "react";
import { diffJson } from "diff";
import type {
  DiffLine,
  SchemaDiffPayload,
  SchemaErrorItem,
  ValidationReport,
} from "../types";
import { useScrollIsolation } from "./useScrollIsolation";

interface Props {
  report?: ValidationReport;
  diff?: SchemaDiffPayload;
  /** Optional human-friendly message above the diff (e.g. server error). */
  message?: string;
}

export const SchemaDiff: React.FC<Props> = ({ report, diff, message }) => {
  const [tab, setTab] = useState<"errors" | "fields" | "raw">("errors");

  const firstRow = report?.errors_by_row?.[0];
  const allErrors: SchemaErrorItem[] = useMemo(
    () => report?.errors_by_row?.flatMap((r) => r.errors) ?? [],
    [report]
  );

  return (
    <section className="card border border-red-500/40 bg-red-950/20 backdrop-blur p-5 sm:p-6 rounded-md">
      <header className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <div className="text-[10px] uppercase tracking-widest text-red-300">
            Schema mismatch
          </div>
          <h3 className="text-base sm:text-lg font-semibold text-red-100 mt-1">
            {message ?? "Upload does not match the Redrob candidate schema"}
          </h3>
          {report && (
            <p className="mt-1 text-xs font-mono text-red-200/80">
              {report.n_invalid} / {report.n_total} records invalid · first bad row #{
                report.first_invalid_index ?? "?"
              }
            </p>
          )}
        </div>
        <nav className="flex text-[11px] uppercase tracking-widest divide-x divide-red-500/30 border border-red-500/30 rounded">
          {(["errors", "fields", "raw"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 transition-colors ${
                tab === t
                  ? "bg-red-500/30 text-red-50"
                  : "text-red-200 hover:bg-red-500/10"
              }`}
            >
              {t}
            </button>
          ))}
        </nav>
      </header>

      {tab === "errors" && <ErrorList errors={allErrors} />}
      {tab === "fields" && diff && <FieldDiff lines={diff.lines} />}
      {tab === "raw" && diff && (
        <RawDiff expected={diff.expected_skeleton} actual={diff.actual} />
      )}
      {tab === "fields" && !diff && (
        <p className="text-xs text-red-200">No diff available for this row.</p>
      )}
    </section>
  );
};

// ───────────────────────── Errors view ─────────────────────────────────────

const codeBadge: Record<SchemaErrorItem["code"], string> = {
  missing_required: "bg-red-500/30 text-red-100 border-red-400/40",
  wrong_type: "bg-amber-500/25 text-amber-100 border-amber-400/40",
  enum_violation: "bg-fuchsia-500/25 text-fuchsia-100 border-fuchsia-400/40",
  out_of_range: "bg-orange-500/25 text-orange-100 border-orange-400/40",
  pattern_mismatch: "bg-rose-500/25 text-rose-100 border-rose-400/40",
  bad_date: "bg-yellow-500/25 text-yellow-100 border-yellow-400/40",
  unknown_property: "bg-emerald-500/25 text-emerald-100 border-emerald-400/40",
  too_few_items: "bg-sky-500/25 text-sky-100 border-sky-400/40",
  too_many_items: "bg-sky-500/25 text-sky-100 border-sky-400/40",
};

const ErrorList: React.FC<{ errors: SchemaErrorItem[] }> = ({ errors }) => {
  const scroll = useScrollIsolation<HTMLUListElement>();
  if (!errors.length)
    return <p className="text-sm text-emerald-300">No schema errors. ✓</p>;
  return (
    <ul
      ref={scroll.ref}
      onWheel={scroll.onWheel}
      className="space-y-2 max-h-[50vh] overflow-auto custom-scroll pr-1"
      style={{ overscrollBehavior: "auto" }}
      data-lenis-prevent
    >
      {errors.map((e, i) => (
        <li
          key={i}
          className="border border-red-500/20 bg-ink-900/50 rounded px-3 py-2 text-xs font-mono"
        >
          <div className="flex items-center justify-between gap-3">
            <code className="text-red-100 truncate">{e.path}</code>
            <span
              className={`pill border ${codeBadge[e.code] ?? "border-red-400/40 text-red-100"}`}
            >
              {e.code.replace(/_/g, " ")}
            </span>
          </div>
          <p className="mt-1 text-red-200/90 leading-relaxed">{e.message}</p>
          {(e.expected || e.actual) && (
            <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
              {e.expected && (
                <div className="bg-emerald-500/10 border-l-2 border-emerald-400 px-2 py-1">
                  <div className="text-[9px] uppercase tracking-widest text-emerald-300">
                    expected
                  </div>
                  <code className="text-emerald-100 break-all">{e.expected}</code>
                </div>
              )}
              {e.actual && (
                <div className="bg-red-500/10 border-l-2 border-red-400 px-2 py-1">
                  <div className="text-[9px] uppercase tracking-widest text-red-300">
                    actual
                  </div>
                  <code className="text-red-100 break-all">{e.actual}</code>
                </div>
              )}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
};

// ───────────────────────── Per-field diff view ─────────────────────────────

const FieldDiff: React.FC<{ lines: DiffLine[] }> = ({ lines }) => {
  // Show missing + extra first, then matches.
  const sorted = useMemo(
    () =>
      [...lines].sort((a, b) => {
        const order = { missing: 0, extra: 1, wrong: 2, match: 3 };
        return order[a.kind] - order[b.kind];
      }),
    [lines]
  );
  const scroll = useScrollIsolation<HTMLDivElement>();
  return (
    <div
      ref={scroll.ref}
      onWheel={scroll.onWheel}
      className="max-h-[55vh] overflow-auto custom-scroll border border-red-500/20 rounded bg-ink-950/70 font-mono text-[12px] leading-relaxed"
      style={{ overscrollBehavior: "auto" }}
      data-lenis-prevent
    >
      {sorted.map((line, i) => (
        <DiffRow key={i} line={line} />
      ))}
    </div>
  );
};

const DiffRow: React.FC<{ line: DiffLine }> = ({ line }) => {
  if (line.kind === "missing") {
    return (
      <div className="flex bg-red-500/10 border-l-2 border-red-500/70">
        <span className="w-6 text-center text-red-300 select-none">-</span>
        <code className="flex-1 px-2 py-0.5 text-red-100">
          {line.path}: <span className="text-red-300/80">{render(line.expected)}</span>{" "}
          <span className="text-red-300/60">// required by schema</span>
        </code>
      </div>
    );
  }
  if (line.kind === "extra") {
    return (
      <div className="flex bg-emerald-500/10 border-l-2 border-emerald-400/70">
        <span className="w-6 text-center text-emerald-300 select-none">+</span>
        <code className="flex-1 px-2 py-0.5 text-emerald-100">
          {line.path}: <span className="text-emerald-300/80">{render(line.actual)}</span>{" "}
          <span className="text-emerald-300/60">// extra / undocumented</span>
        </code>
      </div>
    );
  }
  return (
    <div className="flex">
      <span className="w-6 text-center text-bone-400/60 select-none"> </span>
      <code className="flex-1 px-2 py-0.5 text-bone-300/80">
        {line.path}: <span className="text-bone-400">{render(line.actual)}</span>
      </code>
    </div>
  );
};

function render(value: unknown): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    const s = JSON.stringify(value);
    return s.length > 80 ? s.slice(0, 79) + "…" : s;
  } catch {
    return String(value);
  }
}

// ───────────────────────── Raw side-by-side diff ───────────────────────────

const RawDiff: React.FC<{ expected: unknown; actual: unknown }> = ({
  expected,
  actual,
}) => {
  const parts = useMemo(() => diffJson(expected ?? {}, actual ?? {}), [expected, actual]);
  const scroll = useScrollIsolation<HTMLPreElement>();
  return (
    <pre
      ref={scroll.ref}
      onWheel={scroll.onWheel}
      className="max-h-[55vh] overflow-auto custom-scroll text-[11.5px] leading-snug font-mono bg-ink-950/70 border border-red-500/20 rounded p-3"
      style={{ overscrollBehavior: "auto" }}
      data-lenis-prevent
    >
      {parts.map((part, i) => {
        const cls = part.added
          ? "bg-emerald-500/10 text-emerald-100"
          : part.removed
          ? "bg-red-500/10 text-red-100"
          : "text-bone-300/80";
        const prefix = part.added ? "+ " : part.removed ? "- " : "  ";
        return (
          <span key={i} className={cls}>
            {part.value
              .split("\n")
              .filter((_, idx, arr) => !(idx === arr.length - 1 && _ === ""))
              .map((ln, j) => (
                <span key={j}>
                  {prefix}
                  {ln}
                  {"\n"}
                </span>
              ))}
          </span>
        );
      })}
    </pre>
  );
};

export default SchemaDiff;
