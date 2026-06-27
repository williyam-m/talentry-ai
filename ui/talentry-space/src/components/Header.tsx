import React, { useEffect, useState } from "react";

export const Header: React.FC<{ version?: string }> = ({ version }) => {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`sticky top-0 z-40 transition-all duration-500 backdrop-blur-xl ${
        scrolled
          ? "bg-ink-950/80 border-b border-bone-400/20 shadow-[0_8px_30px_rgba(0,0,0,0.6)]"
          : "bg-transparent border-b border-transparent"
      }`}
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 py-4 flex items-center justify-between">
        <a href="#top" className="flex items-center gap-3 group">
          <Logo />
          <div>
            <h1 className="text-lg sm:text-xl font-semibold tracking-tight bg-gradient-to-r from-bone-50 via-bone-200 to-bone-400 bg-clip-text text-transparent">
              Talentry AI
            </h1>
            <p className="hidden sm:block text-[10px] uppercase tracking-[0.2em] text-bone-400">
              Intelligent Candidate Discovery
            </p>
          </div>
        </a>
        <nav className="flex items-center gap-3 sm:gap-5 text-[11px] uppercase tracking-widest text-bone-300">
          <a
            className="hidden sm:inline relative hover:text-bone-50 transition-colors after:absolute after:left-0 after:-bottom-1 after:h-px after:w-0 after:bg-bone-50 after:transition-all hover:after:w-full"
            href="#how-it-works"
          >
            How it works
          </a>
          <a
            className="relative hover:text-bone-50 transition-colors after:absolute after:left-0 after:-bottom-1 after:h-px after:w-0 after:bg-bone-50 after:transition-all hover:after:w-full"
            href="https://github.com/williyam-m/talentry-ai"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
          </a>
          <a
            className="relative hover:text-bone-50 transition-colors after:absolute after:left-0 after:-bottom-1 after:h-px after:w-0 after:bg-bone-50 after:transition-all hover:after:w-full"
            href="https://williyam-talentry-ai.hf.space"
            target="_blank"
            rel="noreferrer"
          >
            HF Space
          </a>
          {version && (
            <span className="pill border-bone-400/60 text-bone-200 bg-bone-50/5">
              v{version}
            </span>
          )}
        </nav>
      </div>
    </header>
  );
};

const Logo: React.FC = () => (
  <span className="relative inline-flex">
    <svg
      width="34"
      height="34"
      viewBox="0 0 40 40"
      fill="none"
      aria-hidden
      className="relative"
    >
      <rect x="1" y="1" width="38" height="38" stroke="#fafafa" strokeWidth="1.5" />
      <path d="M8 28 L20 8 L32 28 Z" stroke="#fafafa" strokeWidth="1.5" />
      <circle cx="20" cy="22" r="3" fill="#fafafa" />
    </svg>
  </span>
);

