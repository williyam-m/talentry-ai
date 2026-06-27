# Talentry AI - UI Guide

The Talentry HuggingFace Space front-end is a single-page React + TypeScript
application built with Vite and Tailwind. It is intentionally
**black-and-white** (the same restrained palette as `redrob.io`).

---

## 1. Tech stack

| Layer      | Tech                              |
| ---------- | --------------------------------- |
| Framework  | React 18                          |
| Build tool | Vite 5                            |
| Language   | TypeScript 5 (strict)             |
| Styling    | Tailwind CSS 3                    |
| Fonts      | Inter (UI), JetBrains Mono (data) |

No state-management library, no router, no UI library - the UI is intentionally
boring so that the *content* (the ranking explainability) is what stands out.

## 2. Component map

```
src/
├── main.tsx                Bootstrap (React.StrictMode)
├── App.tsx                 Page layout
├── api.ts                  Minimal fetch client (typed)
├── types.ts                Shared TS interfaces matching the API
├── styles.css              Tailwind layers + component classes (.btn, .card, …)
└── components/
    ├── Header.tsx          Brand mark + nav + version pill
    ├── RunPanel.tsx        Candidate / JD upload + Top-K + run buttons
    ├── JdSummary.tsx       Parsed JD card (title, seniority, must-have pills)
    ├── ResultsTable.tsx    Sticky-header ranked-row table; click to drill in
    ├── BreakdownPanel.tsx  Per-component score bars + reasoning sentence
    └── DownloadBar.tsx     CSV download (only when top_k=100)
```

## 3. Local development

```bash
# Backend
make serve              # FastAPI on :7860

# Frontend (in another shell)
make ui-dev             # Vite on :5173, proxies /api -> :7860
```

The UI requires no environment variables in dev; in production (HuggingFace
Space) the SPA is served by the same Uvicorn instance on `:7860`.

## 4. Design language

* **Palette** - `#000000`, `#0a0a0a`, `#141414`, `#fafafa`, `#9a9a9a`.
* **Type** - Inter for UI text, JetBrains Mono for IDs / scores / numbers.
* **Component vocab** - `.card` (hairline border, dark fill), `.pill`
  (tiny tracking-widest tag), `.btn-primary` / `.btn-ghost`.
