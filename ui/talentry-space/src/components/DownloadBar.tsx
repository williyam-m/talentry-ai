import React from "react";
import { csvDownloadUrl } from "../api";

export const DownloadBar: React.FC<{ session: string | null }> = ({ session }) => {
  if (!session) {
    return (
      <div className="text-[11px] text-bone-400 italic">
        Rank with <span className="text-bone-200 font-mono">top_k = 100</span> to unlock the validator-clean CSV download.
      </div>
    );
  }
  return (
    <a className="btn-primary" href={csvDownloadUrl(session)} download>
      ⬇ Download submission.csv
    </a>
  );
};
