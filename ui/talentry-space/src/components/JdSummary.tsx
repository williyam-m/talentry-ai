import React from "react";
import type { JDSummary } from "../types";

export const JdSummary: React.FC<{ jd: JDSummary | null; n: number }> = ({ jd, n }) => {
  if (!jd) return null;
  return (
    <section className="card p-6">
      <h2 className="text-sm uppercase tracking-widest text-bone-300 mb-4">Job description</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <Stat label="Title" value={jd.title} />
        <Stat label="Seniority" value={jd.seniority} />
        <Stat label="Years band" value={`${jd.min_years}–${jd.max_years}`} />
        <Stat label="Pool" value={`${n.toLocaleString()} candidates`} />
      </div>
      <div className="mt-5">
        <div className="text-[11px] uppercase tracking-widest text-bone-400 mb-2">Must-have surface</div>
        <div className="flex flex-wrap gap-1.5">
          {jd.must_have_skills.slice(0, 18).map((s) => (
            <span key={s} className="pill border-bone-400 text-bone-200">{s}</span>
          ))}
        </div>
      </div>
    </section>
  );
};

const Stat: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div>
    <div className="text-[10px] uppercase tracking-widest text-bone-400">{label}</div>
    <div className="font-mono text-bone-50 mt-1">{value}</div>
  </div>
);
