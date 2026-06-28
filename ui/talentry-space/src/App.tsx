/**
 * Talentry AI - application shell.
 *
 * Composition (top → bottom):
 *   <Header/>            sticky logo + nav
 *   <Hero/>              big-type intro
 *   <RunPanel/>          drag-drop + "Feed sample candidates" button
 *   <SchemaPanel/>       collapsible JSON-Schema docs
 *   <SchemaDiff/>        only when /api/rank rejects upload (HTTP 422)
 *   <JdSummary/>         backend's interpretation of the JD
 *   <ResultsTable + Breakdown/>   ranked top-K with explainability
 *   <Storytelling/>      sticky 3D scene + scroll-triggered guide
 *   <ResumeUpload/>      multi-resume → schema-clean records (last section)
 *   <Footer/>
 *
 * Smooth scrolling is provided by Lenis (Stripe-like inertia), and the
 * Storytelling section drives a 3D scene that morphs as the user scrolls
 * through the pipeline steps.
 *
 * IMPORTANT: the Storytelling section is intentionally NOT wrapped in a
 * `.reveal` div with `overflow-hidden` semantics - that would clip the
 * sticky 3D scene as soon as the section came into view.
 */

import React, { useEffect, useState } from "react";
import Lenis from "lenis";
import { Header } from "./components/Header";
import { RunPanel } from "./components/RunPanel";
import { JdSummary } from "./components/JdSummary";
import { ResultsTable } from "./components/ResultsTable";
import { BreakdownPanel } from "./components/BreakdownPanel";
import { DownloadBar } from "./components/DownloadBar";
import { SchemaPanel } from "./components/SchemaPanel";
import { SchemaDiff } from "./components/SchemaDiff";
import { ResumeUpload } from "./components/ResumeUpload";
import { Storytelling } from "./components/storytelling/Storytelling";
import { getHealth, SchemaValidationError } from "./api";
import type { RankResponse, RankedRow } from "./types";

const App: React.FC = () => {
  const [version, setVersion] = useState<string>();
  const [result, setResult] = useState<RankResponse | null>(null);
  const [selected, setSelected] = useState<RankedRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [schemaError, setSchemaError] = useState<SchemaValidationError | null>(null);
  const [prefilledCandidates, setPrefilledCandidates] = useState<File | null>(null);
  const [mouse, setMouse] = useState({ x: 0.5, y: 0.5 });

  // ─── Health probe ─────────────────────────────────────────────────────
  useEffect(() => {
    getHealth()
      .then((h) => setVersion(h.version))
      .catch(() => setVersion(undefined));
  }, []);

  // ─── Auto-select first ranked row ────────────────────────────────────
  useEffect(() => {
    if (result && result.results.length) setSelected(result.results[0]);
  }, [result]);

  // ─── Mouse-driven spotlight + 3D parallax ─────────────────────────────
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      setMouse({
        x: e.clientX / window.innerWidth,
        y: e.clientY / window.innerHeight,
      });
    };
    window.addEventListener("mousemove", onMove, { passive: true });
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  // ─── Lenis smooth scrolling ───────────────────────────────────────────
  // Lenis is intentionally tame: low duration, native wheel multiplier of 1.
  // We also dispatch a native `scroll` event on each Lenis frame so any
  // library that reads from `window.scrollY` (framer-motion's `useScroll`
  // most importantly) stays in sync with the visually-rendered scroll
  // position. Without this the scroll-pinned storytelling section appears
  // to "freeze" because useScroll sees the untouched native scroll position.
  useEffect(() => {
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (prefersReducedMotion) return;
    const lenis = new Lenis({
      duration: 0.9,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
      // Any scrollable element marked `data-lenis-prevent` (the ranked-
      // shortlist scroll box, the schema-diff panels, etc.) keeps its
      // native scroll behaviour instead of having Lenis hijack the wheel.
      prevent: (node) =>
        node instanceof HTMLElement && !!node.closest("[data-lenis-prevent]"),
    });

    let raf = 0;
    const tick = (time: number) => {
      lenis.raf(time);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      lenis.destroy();
    };
  }, []);


  // ─── Reveal-on-scroll for `.reveal` elements ─────────────────────────
  useEffect(() => {
    const els = document.querySelectorAll<HTMLElement>(".reveal");
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("reveal-in");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  });

  // ─── Result/error wiring ─────────────────────────────────────────────
  function handleResult(r: RankResponse) {
    setResult(r);
    setError(null);
    setSchemaError(null);
    // Smooth-scroll to results after a frame so the DOM has time to mount.
    requestAnimationFrame(() => {
      document
        .getElementById("results")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  return (
    <div id="top" className="relative min-h-screen flex flex-col">

      {/* Animated background */}
      <div className="bg-aurora" aria-hidden />
      <div className="bg-grid" aria-hidden />
      <div
        className="bg-spotlight"
        aria-hidden
        style={{
          background: `radial-gradient(600px circle at ${mouse.x * 100}% ${
            mouse.y * 100
          }%, rgba(250,250,250,0.08), transparent 60%)`,
        }}
      />
      <div className="bg-noise" aria-hidden />

      <Header version={version} />

      <main className="relative z-10 mx-auto max-w-7xl w-full px-4 sm:px-6 py-10 md:py-16 flex-1 space-y-12 md:space-y-20">
        {/* ─── Hero ───────────────────────────────────────────────────── */}
        <section className="reveal">
          <div className="inline-flex items-center gap-2 pill border-bone-400/40 text-bone-300 bg-bone-50/5 mb-5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Hybrid retrieval · CPU-only · Zero LLM calls
          </div>
          <h2 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-semibold tracking-tight leading-[1.02]">
            <span className="bg-gradient-to-br from-bone-50 via-bone-100 to-bone-400 bg-clip-text text-transparent">
              The AI brain for modern hiring
            </span>
            <span className="inline-block animate-bounce-slow text-bone-50">!</span>
          </h2>
          <p className="mt-5 text-base sm:text-lg text-bone-300 max-w-2xl">
            BM25 + TF-IDF hybrid ranking with schema-first ingestion, behavioural
            signals, honeypot detection and a fully explainable score
            breakdown. Scaled to <span className="font-mono">millions of candidates</span> with low latency, 0 LLM calls.
          </p>

        </section>

        {/* ─── Run controls ──────────────────────────────────────────── */}
        <div className="reveal">
          <RunPanel
            onResult={handleResult}
            onError={(msg) => {
              setError(msg);
              setSchemaError(null);
            }}
            onSchemaError={(err) => {
              setSchemaError(err);
              setError(null);
            }}
            prefilled={prefilledCandidates}
          />
        </div>

        {/* ─── Schema docs (collapsible) ─────────────────────────────── */}
        <div className="reveal">
          <SchemaPanel />
        </div>

        {/* ─── Schema-validation diff ────────────────────────────────── */}
        {schemaError && (
          <div className="reveal">
            <SchemaDiff
              report={schemaError.payload.report}
              diff={schemaError.payload.diff}
              message={schemaError.payload.message}
            />
          </div>
        )}

        {/* ─── Generic transport error ───────────────────────────────── */}
        {error && (
          <div className="card p-4 text-sm border-red-500/40 text-red-200 reveal">
            {error}
          </div>
        )}

        {/* ─── Results ───────────────────────────────────────────────── */}
        {result && (
          <div id="results" className="space-y-10 scroll-mt-24">
            <div className="reveal">
              <JdSummary jd={result.jd} n={result.n_candidates} />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 reveal">
              <p className="text-xs text-bone-400 font-mono">
                Returned {result.n_returned} of {result.n_candidates} candidates ·
                v{result.version}
              </p>
              <DownloadBar session={result.session_id} />
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 reveal">
              <div className="lg:col-span-2">
                <ResultsTable
                  rows={result.results}
                  onSelect={setSelected}
                  selectedId={selected?.candidate_id ?? null}
                />
              </div>
              <BreakdownPanel row={selected} />
            </div>
          </div>
        )}

        {/*
          ─── Immersive storytelling guide ────────────────────────────
          NOTE: deliberately NOT wrapped in `.reveal` - that wrapper applies a
          CSS transform which establishes a containing block for `position:
          sticky` descendants and would prevent the 3D scene from pinning.
        */}
        <Storytelling />

        {/* ─── Resume uploader (last) ────────────────────────────────── */}
        <div className="reveal">
          <ResumeUpload onParsed={(file) => setPrefilledCandidates(file)} />
        </div>
      </main>

      <section className="relative z-10 mx-auto max-w-7xl w-full px-4 sm:px-6 pb-10">
        <div className="rounded-2xl border border-bone-400/20 bg-gradient-to-br from-ink-900/80 via-ink-950/70 to-ink-900/80 backdrop-blur-xl p-6 md:p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-5">
          <div className="space-y-2 max-w-3xl">
            <p className="text-[10px] uppercase tracking-[0.25em] text-bone-400">
              Open-source side-quest · GRPO
            </p>
            <h3 className="text-lg md:text-xl font-semibold text-bone-50">
              Want an LLM-flavoured candidate ranker?
            </h3>
            <p className="text-sm text-bone-300 leading-relaxed">
              We GRPO-fine-tuned <span className="font-mono text-bone-100">Qwen3-0.6B</span> on
              this very task using a rule-based reward model — no LLM-as-a-judge.
              Pull <span className="font-mono text-bone-100">redrob-qwen-grpo</span> from the
              Hugging Face Hub and plug it into your own pipeline. The Talentry-AI submission
              itself runs without any LLM; this checkpoint is a free, opt-in extra.
            </p>
          </div>
          <a
            href="https://huggingface.co/williyam/redrob-qwen-grpo"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-xl border border-bone-400/40 bg-bone-50/5 hover:bg-bone-50/10 transition-colors px-5 py-3 text-sm font-medium text-bone-50 whitespace-nowrap"
          >
            🤗 Open on Hugging Face →
          </a>
        </div>
      </section>

      <footer className="relative z-10 border-t hairline text-[11px] text-bone-400 px-4 sm:px-6 py-5 mx-auto max-w-7xl w-full flex flex-wrap justify-between gap-3">
        <span>Engineered for explainable, low-latency hiring.</span>
        <span className="font-mono">
          © {new Date().getFullYear()} Williyam M · MIT licensed
        </span>
      </footer>
    </div>
  );
};

export default App;
