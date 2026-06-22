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

  useEffect(() => {
    getHealth()
      .then((h) => setVersion(h.version))
      .catch(() => setVersion(undefined));
  }, []);

  useEffect(() => {
    if (result && result.results.length) setSelected(result.results[0]);
  }, [result]);

  return (
    <div className="min-h-screen flex flex-col">
      <Header version={version} />

      <main className="mx-auto max-w-7xl w-full px-6 py-10 flex-1 space-y-8">
        <section>
          <h2 className="text-4xl md:text-5xl font-semibold tracking-tight leading-[1.05]">
            The AI brain for modern hiring.
          </h2>
          <p className="mt-4 text-bone-300 max-w-2xl">
            Talentry AI turns a 100K candidate ocean into a precise, defensible top‑100 shortlist
            for any job description — with full per-component score explainability, on a CPU laptop,
            in under five minutes, with zero LLM API calls.
          </p>
        </section>

        <RunPanel onResult={(r) => { setResult(r); setError(null); }} onError={setError} />

        {error && (
          <div className="card p-4 text-sm border-red-500/40 text-red-200">{error}</div>
        )}

        {result && (
          <>
            <JdSummary jd={result.jd} n={result.n_candidates} />
            <div className="flex items-center justify-between">
              <p className="text-xs text-bone-400 font-mono">
                Returned {result.n_returned} of {result.n_candidates} candidates · v{result.version}
              </p>
              <DownloadBar session={result.session_id} />
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
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

      <footer className="border-t hairline text-[11px] text-bone-400 px-6 py-5 mx-auto max-w-7xl w-full flex flex-wrap justify-between gap-3">
        <span>
          Built for the <span className="text-bone-200">Redrob × Hack2Skill — India Runs</span> challenge.
        </span>
        <span className="font-mono">© {new Date().getFullYear()} Williyam M · MIT licensed</span>
      </footer>
    </div>
  );
};

export default App;
