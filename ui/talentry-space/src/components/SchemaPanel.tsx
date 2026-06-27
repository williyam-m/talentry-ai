/**
 * Collapsible "Show the schema" panel.
 *
 * Renders the official `candidate_schema.json` (fetched from
 * `/api/schema`) as a navigable tree so users can understand exactly
 * what shape their upload must take. This is what backs the
 * "show candidate schema and a github-like diff" UX in the brief.
 */

import React, { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getSchema } from "../api";

interface SchemaProperty {
  type?: string | string[];
  description?: string;
  enum?: unknown[];
  minimum?: number;
  maximum?: number;
  pattern?: string;
  format?: string;
  required?: string[];
  properties?: Record<string, SchemaProperty>;
  items?: SchemaProperty;
  minItems?: number;
  maxItems?: number;
  additionalProperties?: SchemaProperty | boolean;
}

interface SchemaDoc extends SchemaProperty {
  title?: string;
  description?: string;
}

export const SchemaPanel: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [schema, setSchema] = useState<SchemaDoc | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || schema || loading) return;
    setLoading(true);
    getSchema()
      .then((s) => setSchema(s as SchemaDoc))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [open, schema, loading]);

  return (
    <section className="card-glow p-5 sm:p-6">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-4 text-left group"
        aria-expanded={open}
      >
        <div>
          <div className="text-[10px] uppercase tracking-widest text-bone-400">
            Documentation
          </div>
          <h2 className="text-lg sm:text-xl font-semibold text-bone-50 mt-1">
            Candidate schema
          </h2>
          <p className="text-xs text-bone-400 mt-1">
            The exact shape your <code className="font-mono text-bone-200">.json</code> /{" "}
            <code className="font-mono text-bone-200">.jsonl</code> upload must satisfy.
            We validate every record against this — git diff style report included.

          </p>
        </div>
        <span
          className={`inline-block transition-transform duration-300 text-bone-300 ${
            open ? "rotate-180" : ""
          }`}
          aria-hidden
        >
          ▾
        </span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.35, ease: [0.2, 0.7, 0.2, 1] }}
            className="overflow-hidden"
          >
            <div className="mt-5 border-t hairline pt-5">
              {loading && (
                <p className="text-xs text-bone-400 font-mono">loading schema…</p>
              )}
              {error && (
                <p className="text-xs text-red-300 font-mono">error: {error}</p>
              )}
              {schema && <SchemaTree node={schema} path="$" defaultOpen />}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
};

// ───────────────────────── Recursive tree ──────────────────────────────────

const SchemaTree: React.FC<{
  node: SchemaProperty;
  name?: string;
  path: string;
  required?: boolean;
  defaultOpen?: boolean;
}> = ({ node, name, path, required, defaultOpen }) => {
  const [open, setOpen] = useState(!!defaultOpen);
  const t = Array.isArray(node.type) ? node.type.join(" | ") : node.type;
  const hasChildren =
    (node.properties && Object.keys(node.properties).length > 0) ||
    (node.items && (node.items.properties || node.items.type === "object"));

  const requiredKeys = useMemo(() => new Set(node.required ?? []), [node.required]);

  return (
    <div className="font-mono text-[12.5px] leading-relaxed">
      <button
        onClick={() => hasChildren && setOpen((v) => !v)}
        disabled={!hasChildren}
        className={`group inline-flex items-start gap-2 text-left ${
          hasChildren ? "cursor-pointer" : "cursor-default"
        }`}
      >
        {hasChildren && (
          <span
            className={`text-bone-400 transition-transform ${
              open ? "rotate-90" : ""
            }`}
          >
            ▸
          </span>
        )}
        {!hasChildren && <span className="text-bone-700">·</span>}
        {name && (
          <span className="text-bone-100 group-hover:text-bone-50">{name}</span>
        )}
        {required && (
          <span className="pill border-red-400/40 text-red-200 bg-red-500/10">
            required
          </span>
        )}
        {t && (
          <span className="pill border-bone-400/40 text-bone-300 bg-bone-50/5">
            {t}
            {node.format ? `:${node.format}` : ""}
          </span>
        )}
        {node.enum && (
          <span className="text-bone-400">
            ∈ {`{ ${node.enum.slice(0, 4).map(String).join(", ")}${node.enum.length > 4 ? "…" : ""} }`}
          </span>
        )}
        {(node.minimum !== undefined || node.maximum !== undefined) && (
          <span className="text-bone-400">
            [{node.minimum ?? "−∞"}, {node.maximum ?? "+∞"}]
          </span>
        )}
        {node.pattern && (
          <span className="text-bone-400">/{node.pattern}/</span>
        )}
      </button>
      {node.description && (
        <p className="ml-6 text-bone-400 text-[11.5px] mt-0.5 max-w-3xl">
          {node.description}
        </p>
      )}
      {open && hasChildren && (
        <div className="ml-5 mt-1 border-l hairline pl-3 space-y-1.5">
          {node.properties &&
            Object.entries(node.properties).map(([k, v]) => (
              <SchemaTree
                key={k}
                node={v}
                name={k}
                path={`${path}.${k}`}
                required={requiredKeys.has(k)}
              />
            ))}
          {node.items && (
            <SchemaTree
              node={node.items}
              name={"[items]"}
              path={`${path}[]`}
              defaultOpen={false}
            />
          )}
        </div>
      )}
    </div>
  );
};

export default SchemaPanel;
