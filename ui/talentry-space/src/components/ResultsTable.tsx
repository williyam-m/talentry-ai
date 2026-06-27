import React from "react";
import type { RankedRow } from "../types";

interface Props {
  rows: RankedRow[];
  onSelect: (row: RankedRow) => void;
  selectedId: string | null;
}

export const ResultsTable: React.FC<Props> = ({ rows, onSelect, selectedId }) => (
  <section className="card-glow overflow-hidden">
    <div className="px-6 py-4 border-b hairline flex items-center justify-between">
      <h2 className="text-sm uppercase tracking-widest text-bone-300">
        Ranked shortlist · {rows.length}
      </h2>
      <span className="text-[11px] text-bone-400 font-mono">click a row →</span>
    </div>
    <div
      className="max-h-[60vh] overflow-auto custom-scroll overscroll-contain"
      data-lenis-prevent
    >

      <table className="w-full text-sm border-collapse">
        <thead className="sticky top-0 bg-ink-900/95 backdrop-blur text-bone-400 z-10">
          <tr className="text-left text-[10px] uppercase tracking-widest">
            <th className="px-4 py-3 w-12">#</th>
            <th className="px-4 py-3 w-32">Candidate</th>
            <th className="px-4 py-3 w-20">Score</th>
            <th className="px-4 py-3">Reasoning</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const selected = r.candidate_id === selectedId;
            return (
              <tr
                key={r.candidate_id}
                onClick={() => onSelect(r)}
                className={`row-hover border-t hairline cursor-pointer transition-colors ${
                  selected ? "bg-bone-50 text-ink-950" : ""
                }`}
              >
                <td className="px-4 py-3 font-mono">{r.rank}</td>
                <td className="px-4 py-3 font-mono">{r.candidate_id}</td>
                <td className="px-4 py-3 font-mono">{r.score.toFixed(4)}</td>
                <td
                  className={`px-4 py-3 ${
                    selected ? "text-ink-950" : "text-bone-200"
                  }`}
                >
                  {r.reasoning}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  </section>
);
