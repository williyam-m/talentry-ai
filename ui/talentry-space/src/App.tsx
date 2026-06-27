/**
 * Talentry AI — application shell.
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
 *   <ResumeUpload/>      multi-résumé → schema-clean records (last section)
 *   <Footer/>
 *
 * Smooth scrolling is provided by Lenis (Stripe-like inertia), and the
 * Storytelling section drives a 3D scene that morphs as the user scrolls
 * through the pipeline steps.
 *
 * IMPORTANT: the Storytelling section is intentionally NOT wrapped in a
 * `.reveal` div with `overflow-hidden` semantics — that would clip the
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
  useEffect(() => {
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (prefersReducedMotion) return;
    const lenis = new Lenis({
      duration: 1.1,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
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
    <div id="top" className="relative min-h-screen flex flex-col overflow-x-hidden">
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
            breakdown — 100,000 candidates in under 90 seconds, no GPU, no LLM API calls.
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
          NOTE: deliberately NOT wrapped in `.reveal` — that wrapper applies a
          CSS transform which establishes a containing block for `position:
          sticky` descendants and would prevent the 3D scene from pinning.
        */}
        <Storytelling />

        {/* ─── Résumé uploader (last) ────────────────────────────────── */}
        <div className="reveal">
          <ResumeUpload onParsed={(file) => setPrefilledCandidates(file)} />
        </div>
      </main>

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
