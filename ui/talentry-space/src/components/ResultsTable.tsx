import React, { useRef } from "react";
import type { RankedRow } from "../types";

interface Props {
  rows: RankedRow[];
  onSelect: (row: RankedRow) => void;
  selectedId: string | null;
}

/**
 * Trap wheel + touch scroll inside a scrollable container so that when the
 * user reaches the top or bottom edge the *page* does not start scrolling.
 *
 * `overscroll-behavior: contain` (the CSS-only fix) is honoured by Chrome
 * and Safari but is famously inconsistent on macOS trackpads with inertial
 * scrolling, and Lenis can still pick the wheel event up before the browser
 * applies overscroll-contain. We additionally cancel any wheel delta that
 * would attempt to scroll *past* the container's edges. This is the same
 * pattern used by Linear, Notion's command palette, etc.
 */
function useScrollIsolation<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const onWheel = (e: React.WheelEvent<T>) => {
    const el = ref.current;
    if (!el) return;
    const { scrollTop, scrollHeight, clientHeight } = el;
    const atTop = scrollTop <= 0;
    const atBottom = scrollTop + clientHeight >= scrollHeight - 1;
    // Block bubble-up only when trying to scroll past an edge.
    if ((atTop && e.deltaY < 0) || (atBottom && e.deltaY > 0)) {
      e.preventDefault();
      e.stopPropagation();
    } else {
      // Inside the box — stop propagation so the page (and Lenis) don't
      // also consume the same delta.
      e.stopPropagation();
    }
  };
  return { ref, onWheel };
}

export const ResultsTable: React.FC<Props> = ({ rows, onSelect, selectedId }) => {
  const scroll = useScrollIsolation<HTMLDivElement>();
  return (
  <section className="card-glow overflow-hidden">
    <div className="px-6 py-4 border-b hairline flex items-center justify-between">
      <h2 className="text-sm uppercase tracking-widest text-bone-300">
        Ranked shortlist · {rows.length}
      </h2>
      <span className="text-[11px] text-bone-400 font-mono">click a row →</span>
    </div>
    <div
      ref={scroll.ref}
      onWheel={scroll.onWheel}
      className="max-h-[60vh] overflow-auto custom-scroll overscroll-contain"
      style={{ overscrollBehavior: "contain" }}
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
};

