import React, { useEffect, useState } from "react";
import { Header } from "./components/Header";
import { RunPanel } from "./components/RunPanel";
import { JdSummary } from "./components/JdSummary";
import { ResultsTable } from "./components/ResultsTable";
import { BreakdownPanel } from "./components/BreakdownPanel";
import { DownloadBar } from "./components/DownloadBar";
import { getHealth } from "./api";
import type { RankResponse, RankedRow } from "./types";

const App: React.FC = () => {
  const [version, setVersion] = useState<string>();
  const [result, setResult] = useState<RankResponse | null>(null);
  const [selected, setSelected] = useState<RankedRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mouse, setMouse] = useState({ x: 0.5, y: 0.5 });

  useEffect(() => {
    getHealth()
      .then((h) => setVersion(h.version))
      .catch(() => setVersion(undefined));
  }, []);

  useEffect(() => {
    if (result && result.results.length) setSelected(result.results[0]);
  }, [result]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      setMouse({
        x: e.clientX / window.innerWidth,
        y: e.clientY / window.innerHeight,
      });
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  // Reveal-on-scroll
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

      <main className="relative z-10 mx-auto max-w-7xl w-full px-4 sm:px-6 py-10 md:py-16 flex-1 space-y-10 md:space-y-14">
        <section className="reveal">
          <div className="inline-flex items-center gap-2 pill border-bone-400/40 text-bone-300 bg-bone-50/5 mb-5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Explainable · CPU-only · Zero LLM calls
          </div>
          <h2 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-semibold tracking-tight leading-[1.02]">
            <span className="bg-gradient-to-br from-bone-50 via-bone-100 to-bone-400 bg-clip-text text-transparent">
              The AI brain for modern hiring
            </span>
            <span className="inline-block animate-bounce-slow text-bone-50">!</span>
          </h2>
          <p className="mt-5 text-base sm:text-lg text-bone-300 max-w-2xl">
            Rank candidates. Explain every score.
          </p>
        </section>

        <div className="reveal">
          <RunPanel onResult={(r) => { setResult(r); setError(null); }} onError={setError} />
        </div>

        {error && (
          <div className="card p-4 text-sm border-red-500/40 text-red-200 reveal">{error}</div>
        )}

        {result && (
          <>
            <div className="reveal">
              <JdSummary jd={result.jd} n={result.n_candidates} />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 reveal">
              <p className="text-xs text-bone-400 font-mono">
                Returned {result.n_returned} of {result.n_candidates} candidates · v{result.version}
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
          </>
        )}
      </main>

      <footer className="relative z-10 border-t hairline text-[11px] text-bone-400 px-4 sm:px-6 py-5 mx-auto max-w-7xl w-full flex flex-wrap justify-between gap-3">
        <span>Crafted with care for explainable hiring.</span>
        <span className="font-mono">© {new Date().getFullYear()} Williyam M · MIT licensed</span>
      </footer>
    </div>
  );
};

export default App;
