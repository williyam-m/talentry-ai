"""Production entry-point used by the HuggingFace Space.

Mounts the Vite-built SPA on / and the FastAPI JSON API on /api.

The SPA directory is searched in two locations so the same script works
both for local development (``ui/talentry-space/dist``) and the Docker
image (``./ui_dist`` next to the script).
"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi.staticfiles import StaticFiles

from talentry.api.server import app

_HERE = Path(__file__).resolve().parent
_CANDIDATES = (
    _HERE / "ui_dist",
    _HERE.parent / "ui_dist",
    _HERE.parent / "ui" / "talentry-space" / "dist",
)
SPA = next((p for p in _CANDIDATES if p.exists() and (p / "index.html").exists()), None)
if SPA is not None:
    # html=True falls back to index.html for SPA client routes.
    app.mount("/", StaticFiles(directory=str(SPA), html=True), name="ui")
    print(f"[serve] mounted SPA from {SPA}")
else:
    print("[serve] no SPA build found; API-only mode")

if __name__ == "__main__":
    host = os.getenv("TALENTRY_HOST", "0.0.0.0")
    port = int(os.getenv("TALENTRY_PORT", "7860"))
    uvicorn.run(app, host=host, port=port, log_level="info")
