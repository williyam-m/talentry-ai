import React from "react";

export const Header: React.FC<{ version?: string }> = ({ version }) => (
  <header className="border-b hairline">
    <div className="mx-auto max-w-7xl px-6 py-5 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <Logo />
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Talentry AI</h1>
          <p className="text-[11px] uppercase tracking-widest text-bone-400">
            Intelligent Candidate Discovery & Ranking
          </p>
        </div>
      </div>
      <nav className="flex items-center gap-4 text-xs uppercase tracking-widest text-bone-300">
        <a className="hover:text-bone-50" href="https://github.com/williyam-m/talentry-ai" target="_blank" rel="noreferrer">
          GitHub
        </a>
        <a className="hover:text-bone-50" href="https://huggingface.co/spaces/williyam/talentry-ai" target="_blank" rel="noreferrer">
          HF Space
        </a>
        {version && <span className="pill border-bone-400 text-bone-300">v{version}</span>}
      </nav>
    </div>
  </header>
);

const Logo: React.FC = () => (
  <svg width="34" height="34" viewBox="0 0 40 40" fill="none" aria-hidden>
    <rect x="1" y="1" width="38" height="38" stroke="#fafafa" strokeWidth="1.5" />
    <path d="M8 28 L20 8 L32 28 Z" stroke="#fafafa" strokeWidth="1.5" />
    <circle cx="20" cy="22" r="3" fill="#fafafa" />
  </svg>
);
