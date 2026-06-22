# syntax=docker/dockerfile:1.6
# ──────────────────────────────────────────────────────────────────────────────
#  Talentry AI · HuggingFace Space image
#  ─────────────────────────────────────
#  Stage 1: build the React + Vite + Tailwind UI to static assets.
#  Stage 2: install the Python ranker, copy the built UI in, and serve both
#           the JSON API and the static SPA on port 7860 (the HF default).
# ──────────────────────────────────────────────────────────────────────────────

FROM node:20-bookworm-slim AS ui-build
WORKDIR /ui
COPY ui/talentry-space/package.json ui/talentry-space/package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm \
    npm install --no-audit --no-fund
COPY ui/talentry-space/ ./
RUN npm run build


FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TALENTRY_HOST=0.0.0.0 \
    TALENTRY_PORT=7860 \
    HF_HOME=/tmp/hf

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY data/raw ./data/raw

RUN pip install --upgrade pip && pip install ".[api]"

# Copy compiled SPA + tell FastAPI where to find it.
COPY --from=ui-build /ui/dist ./ui_dist
COPY scripts/serve.py ./serve.py

EXPOSE 7860
CMD ["python", "serve.py"]
