/**
 * Submission download bar - both CSV (validator-friendly) and XLSX
 * (reviewer-friendly) are exposed because the hackathon spec accepts either.
 */

import React from "react";
import { csvDownloadUrl, xlsxDownloadUrl } from "../api";

export const DownloadBar: React.FC<{ session: string | null }> = ({ session }) => {
  if (!session) {
    return (
      <span className="text-[11px] text-bone-400 italic">
        Run the ranker to enable submission download.
      </span>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <a className="btn-primary group relative overflow-hidden" href={csvDownloadUrl(session)} download>
        <span className="relative z-10 flex items-center gap-2">
          <DownloadIcon />
          submission.csv
        </span>
        <span className="absolute inset-0 bg-bone-200 translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
      </a>
      <a className="btn-ghost group relative overflow-hidden" href={xlsxDownloadUrl(session)} download>
        <span className="relative z-10 flex items-center gap-2">
          <DownloadIcon />
          submission.xlsx
        </span>
      </a>
    </div>
  );
};

const DownloadIcon: React.FC = () => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    className="transition-transform group-hover:translate-y-0.5"
  >
    <path d="M12 3v12m0 0l-4-4m4 4l4-4M5 21h14" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
