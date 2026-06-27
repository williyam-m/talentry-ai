/**
 * Immersive, scroll-triggered storytelling section.
 *
 * Architecture
 * ────────────
 * One tall outer wrapper (height = N * 100vh) hosts a single sticky inner
 * stage that is pinned to the viewport while the user scrolls through it.
 * The active step is derived from the wrapper's scroll progress via
 * framer-motion's useScroll + useTransform, which is the same pattern that
 * powers patronus.ai and scale.com - it never "unpins early" because the
 * sticky element has no siblings competing for the grid track.
 *
 * The text column on the left fades in/out per step (crossfaded), and the
 * right column hosts the 3D scene that morphs as `step` changes.
 *
 * Why not IntersectionObserver? Because IO fires on viewport intersection
 * and stops as soon as the section scrolls past the top - that is exactly
 * the "scene goes away after step 1" bug we were seeing.
 */

import React, { useMemo, useRef } from "react";
import {
  motion,
  useMotionValueEvent,
  useScroll,
  useTransform,
} from "framer-motion";
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
      "record at a time and normalises each into a slotted dataclass mirroring " +
      "the official Redrob schema 1:1, so downstream stages never re-parse raw JSON.",
    stack: ["orjson", "gzip streaming", "slotted dataclasses", "schema-aligned DTOs"],
  },
  {
    id: "validate",
    kicker: "02 · Validate",
    title: "Schema-first, fail-fast contract",
    body:
      "Every record is checked against a focused draft-07 JSON-Schema validator. " +
      "Mismatches surface as a git diff style report (added / removed / changed " +
      "lines) for missing required fields, unknown fields, and enum / type / " +
      "range violations. Bad data is rejected before any token is scored.",
    stack: ["JSON-Schema draft-07", "deterministic walker", "git-diff payload", "HTTP 422"],
  },
  {
    id: "understand",
    kicker: "03 · Understand the JD",
    title: "Hybrid retrieval, not keyword bingo",
    body:
      "The JD is parsed into a JobRequirements DTO (role family, seniority band, " +
      "must / nice-have / disqualifier skills). Candidates are scored with a hybrid " +
      "of BM25 + TF-IDF + role-lexicon evidence so a senior who writes \"I built " +
      "distributed training on 8 x A100\" outranks the \"PyTorch expert\" who just " +
      "stuffed the skill list.",
    stack: ["rank_bm25", "scikit-learn TF-IDF", "role lexicon graph", "RapidFuzz"],
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
    stack: ["signal lexicon", "honeypot rules", "behavioural priors", "endorsement trust"],
  },
  {
    id: "ship",
    kicker: "05 · Ship",
    title: "Explainable shortlist + validator-clean CSV",
    body:
      "The final top-K is materialised with a per-candidate score breakdown and " +
      "a 1-2 sentence justification that cites real facts. The same payload is " +
      "written to a validator-clean submission.csv served via " +
      "/api/submission.csv?session=...",
    stack: ["FastAPI", "GZip middleware", "LRU result cache", "validator-clean CSV"],
  },
];

export const Storytelling: React.FC = () => {
  const sectionRef = useRef<HTMLDivElement>(null);
  const stickyRef = useRef<HTMLDivElement>(null);

  // Each step occupies one viewport-height of scroll.
  const N = STEPS.length;
  const heightVh = N * 100;

  // Progress is 0 at the top of the section (sticky just attached) and 1
  // when the last viewport has scrolled past the bottom of the sticky.
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    // start when the section's top reaches the viewport top,
    // end when the bottom reaches the viewport bottom.
    offset: ["start start", "end end"],
  });

  // Derive a discrete active index (0..N-1) from the continuous progress.
  const activeMV = useTransform(scrollYProgress, (p) =>
    Math.min(N - 1, Math.max(0, Math.floor(p * N)))
  );

  const [active, setActive] = React.useState(0);
  useMotionValueEvent(activeMV, "change", (v) => {
    const i = Math.round(v as number);
    setActive((cur) => (cur === i ? cur : i));
  });

  // Mouse parallax for the 3D scene.
  const [parallax, setParallax] = React.useState({ x: 0, y: 0 });
  React.useEffect(() => {
    function onMove(e: MouseEvent) {
      setParallax({
        x: (e.clientX / window.innerWidth) * 2 - 1,
        y: (e.clientY / window.innerHeight) * 2 - 1,
      });
    }
    window.addEventListener("mousemove", onMove, { passive: true });
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  const current = useMemo(() => STEPS[active], [active]);

  return (
    <section id="how-it-works" className="relative">
      {/* ── Intro ──────────────────────────────────────────────────── */}
      <div className="mx-auto max-w-7xl px-4 sm:px-6 mb-10 md:mb-14">
        <div className="inline-flex items-center gap-2 pill border-bone-400/40 text-bone-300 bg-bone-50/5">
          <span className="w-1.5 h-1.5 rounded-full bg-bone-50 animate-pulse" />
          How Talentry works
        </div>
        <h2 className="mt-4 text-3xl sm:text-4xl md:text-5xl font-semibold tracking-tight bg-gradient-to-br from-bone-50 via-bone-100 to-bone-400 bg-clip-text text-transparent max-w-3xl">
          100K resumes to a defensible shortlist. Every stage, instrumented.
        </h2>
        <p className="mt-4 text-bone-300 text-sm sm:text-base max-w-2xl">
          Scroll to walk the pipeline. The geometry on the right reshapes
          itself as the candidate pool is refined.
        </p>
      </div>

      {/* ── Scroll-pinned stage ───────────────────────────────────── */}
      <div
        ref={sectionRef}
        className="relative"
        style={{ height: `${heightVh}vh` }}
      >
        <div
          ref={stickyRef}
          className="sticky top-0 h-screen flex items-center"
        >
          <div className="mx-auto max-w-7xl w-full px-4 sm:px-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12 items-center">
              {/* ── Left: crossfaded text ─────────────────────────── */}
              <div className="relative h-[72vh]">
                {STEPS.map((s, i) => (
                  <motion.div
                    key={s.id}
                    initial={false}
                    animate={{
                      opacity: active === i ? 1 : 0,
                      y: active === i ? 0 : 16,
                    }}
                    style={{ pointerEvents: active === i ? "auto" : "none" }}
                    transition={{ duration: 0.55, ease: [0.2, 0.7, 0.2, 1] }}
                    className="absolute inset-0 flex flex-col justify-center max-w-xl"
                  >

                    <div className="text-[11px] uppercase tracking-[0.25em] text-bone-400">
                      {s.kicker}
                    </div>
                    <h3 className="mt-3 text-2xl sm:text-3xl md:text-4xl font-semibold text-bone-50 leading-tight">
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
                    {/* Progress rail */}
                    <div className="mt-8 flex items-center gap-2">
                      {STEPS.map((_, j) => (
                        <span
                          key={j}
                          className={`h-[2px] transition-all duration-500 ${
                            j === active
                              ? "w-10 bg-bone-50"
                              : j < active
                              ? "w-6 bg-bone-300/60"
                              : "w-6 bg-bone-700/60"
                          }`}
                        />
                      ))}
                      <span className="ml-2 text-[10px] font-mono text-bone-400">
                        {active + 1}/{N}
                      </span>
                    </div>
                  </motion.div>
                ))}
              </div>

              {/* ── Right: 3D scene (does NOT move while pinned) ──── */}
              <aside className="hidden md:block">
                <div className="relative h-[72vh] rounded-md overflow-hidden border hairline bg-ink-950/80">
                  <Scene3D step={active} parallax={parallax} />
                  <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-ink-950/80 via-transparent to-ink-950/20" />
                  <StackOverlay step={current} index={active + 1} total={N} />
                </div>
              </aside>
            </div>
          </div>
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
    <motion.div
      key={step.id}
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="card px-3 py-2 max-w-[80%] backdrop-blur"
    >
      <div className="text-[10px] uppercase tracking-widest text-bone-400">
        {step.kicker}
      </div>
      <div className="text-xs font-mono text-bone-100 mt-0.5">{step.title}</div>
    </motion.div>
    <div className="pill border-bone-400/40 text-bone-300 bg-ink-900/60 backdrop-blur">
      {index} / {total}
    </div>
  </div>
);

export default Storytelling;
