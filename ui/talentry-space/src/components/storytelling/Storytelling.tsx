/**
 * Immersive, scroll-triggered storytelling section.
 *
 * Layout
 * ──────
 * A single CSS grid with two columns (≥ md):
 *   • LEFT  → vertical stack of N narrative "steps", each ~ a screen tall.
 *   • RIGHT → ONE element whose `position: sticky` pins it to the viewport
 *             while the user scrolls through the left-hand steps. That
 *             element hosts the <Scene3D/> + a per-step caption overlay.
 *
 * IMPORTANT: `position: sticky` only works while inside the grid container.
 * Once the user scrolls past the last step, the sticky element naturally
 * "unpins" — which is the correct behaviour (the 3D scene exits with the
 * section instead of overlaying the rest of the page).
 *
 * The active step is driven by an IntersectionObserver biased toward the
 * centre of the viewport, mirroring the patronus.ai / scale.com pattern.
 */

import React, { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Scene3D } from "./Scene3D";

interface StoryStep {
  id: string;
  kicker: string;
  title: string;
  body: string;
  /** Tech / techniques used at this stage of the pipeline. */
  stack: string[];
}

const STEPS: StoryStep[] = [
  {
    id: "ingest",
    kicker: "01 · Ingest",
    title: "Stream 100K candidates at line-rate",
    body:
      "A zero-copy streaming loader pulls JSONL / JSON / JSONL.gz off disk one " +
      "record at a time and normalises each into a slotted Python dataclass mirroring " +
      "the official Redrob schema 1:1, so downstream stages never re-parse raw JSON.",
    stack: ["orjson", "gzip streaming", "Python dataclasses (slots)", "schema-aligned DTOs"],
  },
  {
    id: "validate",
    kicker: "02 · Validate",
    title: "Schema-first — git diff style report before scoring",
    body:
      "Every record is checked against a focused draft-07 JSON-Schema validator. " +
      "Mismatches are surfaced as a git diff style report — added / removed / changed " +
      "lines for missing required fields, unknown fields, and enum / type violations. " +
      "Bad data is rejected before any token is scored.",
    stack: ["JSON-Schema (draft-07)", "deterministic walker", "git diff style report", "fail-fast contract"],
  },
  {
    id: "understand",
    kicker: "03 · Understand the JD",
    title: "Hybrid retrieval — not keyword bingo",
    body:
      "The Job Description is parsed into a structured JobRequirements DTO " +
      "(role family, seniority band, must / nice-have / disqualifier skills). " +
      "Candidates are scored with a hybrid of BM25 + TF-IDF + role-lexicon evidence — " +
      "a senior who writes \"I built distributed training on 8×A100\" outranks the " +
      '"PyTorch expert" who just stuffed the skill list.',
    stack: ["rank_bm25", "scikit-learn TF-IDF", "role lexicon graph", "RapidFuzz fuzzy match"],
  },
  {
    id: "signals",
    kicker: "04 · Behavioural signals",
    title: "Reading between the lines",
    body:
      "Profile completeness, response rate, search appearance, GitHub activity, " +
      "endorsement trust and honeypot detectors combine into multiplicative and " +
      "subtractive modifiers. Inactive paper-perfect profiles get penalised; " +
      "verified, responsive, active candidates get rewarded.",
    stack: ["custom signal lexicon", "honeypot rules", "behavioural priors", "endorsement trust"],
  },
  {
    id: "ship",
    kicker: "05 · Ship",
    title: "Explainable shortlist + validator-clean CSV",
    body:
      "The final top-K is materialised with a per-candidate score breakdown and a " +
      "natural-language justification. The same payload is also written to a " +
      "validator-clean submission.csv served via /api/submission.csv?session=…",
    stack: ["FastAPI", "GZip middleware", "LRU result cache", "validator-clean CSV"],
  },
];

export const Storytelling: React.FC = () => {
  const [active, setActive] = useState(0);
  const [parallax, setParallax] = useState({ x: 0, y: 0 });
  const stepRefs = useRef<(HTMLElement | null)[]>([]);

  // ── Drive `active` from intersection with the viewport's middle band ──
  useEffect(() => {
    const els = stepRefs.current.filter(Boolean) as HTMLElement[];
    if (!els.length) return;
    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) {
          const idx = Number((visible[0].target as HTMLElement).dataset.idx);
          if (!Number.isNaN(idx)) setActive(idx);
        }
      },
      { rootMargin: "-35% 0px -40% 0px", threshold: [0, 0.25, 0.5, 0.75, 1] }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  // ── Mouse parallax for the 3D scene ──────────────────────────────────
  useEffect(() => {
    function onMove(e: MouseEvent) {
      setParallax({
        x: (e.clientX / window.innerWidth) * 2 - 1,
        y: (e.clientY / window.innerHeight) * 2 - 1,
      });
    }
    window.addEventListener("mousemove", onMove, { passive: true });
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  const current = STEPS[active];

  return (
    <section id="how-it-works" className="relative">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        {/* ── Section intro ─────────────────────────────────────────── */}
        <div className="mb-10 md:mb-16 reveal">
          <div className="inline-flex items-center gap-2 pill border-bone-400/40 text-bone-300 bg-bone-50/5">
            <span className="w-1.5 h-1.5 rounded-full bg-bone-50 animate-pulse" />
            How Talentry works
          </div>
          <h2 className="mt-4 text-3xl sm:text-4xl md:text-5xl font-semibold tracking-tight bg-gradient-to-br from-bone-50 via-bone-100 to-bone-400 bg-clip-text text-transparent max-w-3xl">
            From 100,000 résumés to a defensible shortlist — every stage, instrumented.
          </h2>
          <p className="mt-4 text-bone-300 text-sm sm:text-base max-w-2xl">
            Scroll to walk through the pipeline. The geometry on the right
            reshapes itself as the candidate pool is refined.
          </p>
        </div>

        {/* ── Sticky 3D + scrolling text ───────────────────────────── */}
        {/*
          NOTE: `items-start` is critical. Without it the grid stretches both
          columns to the same height and sticky cannot work on the right one.
        */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12 items-start">
          {/* RIGHT column first in source order so we can re-order it on
              mobile (text first, scene below) while keeping the source
              easy to read. On md+ we put the scene on the right with
              `md:order-2` and the text on the left with `md:order-1`. */}

          {/* Sticky 3D scene */}
          <aside className="hidden md:block md:order-2">
            <div
              className="sticky top-24 h-[78vh] rounded-md overflow-hidden border hairline bg-ink-950/80 relative"
              // `will-change: transform` keeps Safari's sticky implementation honest.
              style={{ willChange: "transform" }}
            >
              <Scene3D step={active} parallax={parallax} />
              <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-ink-950/80 via-transparent to-ink-950/20" />
              <StackOverlay step={current} index={active + 1} total={STEPS.length} />
            </div>
          </aside>

          {/* Scrolling steps */}
          <ol className="md:order-1 space-y-0">
            {STEPS.map((s, i) => (
              <li
                key={s.id}
                data-idx={i}
                ref={(el) => (stepRefs.current[i] = el)}
                className="min-h-[80vh] flex items-center"
              >
                <motion.div
                  initial={{ opacity: 0.2, y: 24 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ amount: 0.4, once: false }}
                  transition={{ duration: 0.6, ease: [0.2, 0.7, 0.2, 1] }}
                  animate={{ opacity: active === i ? 1 : 0.45 }}
                  className="max-w-xl"
                >
                  <div className="text-[11px] uppercase tracking-[0.25em] text-bone-400">
                    {s.kicker}
                  </div>
                  <h3 className="mt-3 text-2xl sm:text-3xl font-semibold text-bone-50 leading-tight">
                    {s.title}
                  </h3>
                  <p className="mt-4 text-bone-300 text-sm sm:text-base leading-relaxed">
                    {s.body}
                  </p>
                  <div className="mt-5 flex flex-wrap gap-1.5">
                    {s.stack.map((t) => (
                      <span
                        key={t}
                        className="pill border-bone-400/40 text-bone-200 bg-bone-50/5"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </motion.div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
};

// ─────────────────────────────────────────────────────────────────────────────

const StackOverlay: React.FC<{ step: StoryStep; index: number; total: number }> = ({
  step,
  index,
  total,
}) => (
  <div className="absolute top-4 left-4 right-4 flex items-start justify-between gap-3">
    <AnimatePresence mode="wait">
      <motion.div
        key={step.id}
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.35 }}
        className="card px-3 py-2 max-w-[80%] backdrop-blur"
      >
        <div className="text-[10px] uppercase tracking-widest text-bone-400">
          {step.kicker}
        </div>
        <div className="text-xs font-mono text-bone-100 mt-0.5">{step.title}</div>
      </motion.div>
    </AnimatePresence>
    <div className="pill border-bone-400/40 text-bone-300 bg-ink-900/60 backdrop-blur">
      {index} / {total}
    </div>
  </div>
);

export default Storytelling;
