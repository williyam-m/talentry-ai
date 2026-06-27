/**
 * Immersive, scroll-triggered storytelling section.
 *
 * Layout:
 *   • A 100vh sticky panel on the right (≥ md) holding the 3D <Scene3D/>.
 *   • A stack of 5 narrative "steps" on the left, each ~80vh tall.
 *     As the user scrolls, an IntersectionObserver promotes one step at a
 *     time to `active`; the active step drives:
 *       - Scene3D `step` prop (geometry / colour morph)
 *       - the floating "tech stack" caption block on top-right
 *       - per-step framer-motion enter animations
 *
 * Strategic-storytelling references in the brief: patronus.ai, scale.com.
 * Both ship one sticky hero canvas + scrolling text alongside; we replicate
 * that pattern with our own ranking pipeline narrative.
 */

import React, { useEffect, useMemo, useRef, useState } from "react";
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
    title: "100,000 candidates — streamed, not loaded",
    body:
      "We ingest JSONL/JSON/JSONL.gz at line-rate with a zero-copy streaming loader. " +
      "Each record is normalised into a slotted Python dataclass that mirrors the " +
      "official Redrob schema 1:1 — so the rest of the pipeline never re-reads raw JSON.",
    stack: ["orjson", "gzip streaming", "Python dataclasses (slots)", "candidate_schema.json"],
  },
  {
    id: "validate",
    kicker: "02 · Validate",
    title: "Schema-first — green/red diff before a single token is scored",
    body:
      "Every record is checked against a focused draft-07 JSON-Schema validator. " +
      "Mismatches are surfaced as a GitHub-style diff: red lines for missing required " +
      "fields, green for fields the schema doesn't declare. Bad data never reaches the ranker.",
    stack: ["JSON-Schema (draft-07)", "deterministic walker", "GitHub-style diff", "fail-fast"],
  },
  {
    id: "understand",
    kicker: "03 · Understand the JD",
    title: "Hybrid retrieval, not keyword bingo",
    body:
      "The Job Description is parsed into a structured JobRequirements object " +
      "(role family, seniority, must/nice-have skills). Candidates are then scored " +
      "with a hybrid of BM25 + TF-IDF + role-keyword evidence — so a senior who writes " +
      '"I built distributed training on 8×A100" beats a keyword stuffer claiming "PyTorch expert".',
    stack: ["rank_bm25", "scikit-learn TF-IDF", "role lexicon", "RapidFuzz"],
  },
  {
    id: "signals",
    kicker: "04 · Behavioural signals",
    title: "Reading between the lines",
    body:
      "Profile completeness, response-rate, search-appearance, GitHub activity, " +
      "honeypot detectors — all combined into multiplicative & subtractive modifiers. " +
      "Inactive paper-perfect candidates get penalised; verified, responsive, active " +
      "ones get rewarded.",
    stack: ["custom signal lexicon", "honeypot rules", "behavioural priors"],
  },
  {
    id: "ship",
    kicker: "05 · Ship",
    title: "Explainable shortlist + CSV in <90 s on a laptop",
    body:
      "The final top-K is materialised with a per-candidate score breakdown and a " +
      "natural-language reasoning line. The same payload is also written to a " +
      "validator-clean submission.csv served via /api/submission.csv?session=…",
    stack: ["FastAPI", "GZip middleware", "LRU result cache", "validator-clean CSV"],
  },
];

export const Storytelling: React.FC = () => {
  const [active, setActive] = useState(0);
  const [parallax, setParallax] = useState({ x: 0, y: 0 });
  const stepRefs = useRef<(HTMLElement | null)[]>([]);

  useEffect(() => {
    const els = stepRefs.current.filter(Boolean) as HTMLElement[];
    if (!els.length) return;
    const io = new IntersectionObserver(
      (entries) => {
        // Pick the entry with greatest intersectionRatio that is currently visible.
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) {
          const idx = Number((visible[0].target as HTMLElement).dataset.idx);
          if (!Number.isNaN(idx)) setActive(idx);
        }
      },
      {
        // Bias the observer toward the centre of the viewport.
        rootMargin: "-30% 0px -40% 0px",
        threshold: [0.25, 0.5, 0.75],
      }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

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
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6">
        <div className="mb-10 md:mb-16 reveal">
          <div className="inline-flex items-center gap-2 pill border-bone-400/40 text-bone-300 bg-bone-50/5">
            <span className="w-1.5 h-1.5 rounded-full bg-bone-50 animate-pulse" />
            How Talentry works
          </div>
          <h2 className="mt-4 text-3xl sm:text-4xl md:text-5xl font-semibold tracking-tight bg-gradient-to-br from-bone-50 via-bone-100 to-bone-400 bg-clip-text text-transparent max-w-3xl">
            From 100,000 résumés to a defensible shortlist — every step, explained.
          </h2>
          <p className="mt-4 text-bone-300 text-sm sm:text-base max-w-2xl">
            Scroll to walk through the pipeline. The geometry on the right
            reshapes itself as the candidate pool gets refined.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12">
          {/* Left: scrolling steps */}
          <ol className="relative space-y-[55vh] pb-[50vh]">
            {STEPS.map((s, i) => (
              <li
                key={s.id}
                data-idx={i}
                ref={(el) => (stepRefs.current[i] = el)}
                className="min-h-[40vh]"
              >
                <motion.div
                  initial={{ opacity: 0.25, y: 24 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ amount: 0.5, once: false }}
                  transition={{ duration: 0.6, ease: [0.2, 0.7, 0.2, 1] }}
                  className={`max-w-xl ${active === i ? "" : "opacity-60"}`}
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

          {/* Right: sticky 3D scene */}
          <aside className="hidden md:block">
            <div className="sticky top-24 h-[80vh] rounded-md overflow-hidden border hairline bg-ink-950/80 relative">
              <Scene3D step={active} parallax={parallax} />
              <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-ink-950/80 via-transparent to-ink-950/20" />
              <StackOverlay step={current} index={active + 1} total={STEPS.length} />
            </div>
          </aside>
        </div>
      </div>
    </section>
  );
};

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
