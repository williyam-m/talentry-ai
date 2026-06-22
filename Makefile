# Talentry AI — common dev tasks
PY ?= python3
VENV ?= .venv

.PHONY: help venv install lint test smoke submission ui-dev serve docker-build docker-run clean

help:
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*##"}{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

venv: ## create the python venv
	$(PY) -m venv $(VENV)

install: ## editable install with dev extras
	$(VENV)/bin/pip install -U pip
	$(VENV)/bin/pip install -e ".[dev]"

lint: ## ruff + black check
	$(VENV)/bin/ruff check src tests
	$(VENV)/bin/black --check src tests

test: ## run unit tests
	$(VENV)/bin/pytest -q

smoke: ## end-to-end run on the 50-row fixture (top_k=10, non-strict)
	$(VENV)/bin/python -m talentry.cli.rank \
		--candidates data/raw/sample_candidates.json \
		--out data/output/smoke.csv --top-k 10 --quiet
	@head -1 data/output/smoke.csv && echo "..." && wc -l data/output/smoke.csv

submission: ## produce the 100-row hackathon CSV (needs data/raw/candidates.jsonl)
	$(VENV)/bin/python -m talentry.cli.rank \
		--candidates data/raw/candidates.jsonl \
		--jd configs/job_description.txt \
		--out data/output/submission.csv

ui-dev: ## run the React UI in dev mode (proxies /api -> :7860)
	cd ui/talentry-space && npm install && npm run dev

serve: ## run the FastAPI dev server on :7860
	$(VENV)/bin/talentry-serve

docker-build: ## build the HuggingFace Space image
	docker build -t talentry-ai:dev .

docker-run: ## run the Docker image locally on :7860
	docker run --rm -p 7860:7860 talentry-ai:dev

clean: ## remove build artefacts
	rm -rf build dist *.egg-info data/output
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
