.PHONY: install sandbox backend frontend demo test smoke replay help

PYTHON ?= python
PIP ?= pip
NPM ?= npm

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install Python + Node dependencies
	$(PIP) install -r requirements.txt
	@if [ -d frontend/package.json ]; then cd frontend && $(NPM) install; fi

sandbox: ## Serve the sandbox shop on port 8001 (M4 builds this)
	$(PYTHON) -m http.server 8001 --directory sandbox/site

backend: ## Start the FastAPI backend on port 8000
	USE_STUBS=$(USE_STUBS) $(PYTHON) -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

frontend: ## Start the frontend dev server on port 5173 (M4 builds this)
	@if [ -f frontend/package.json ]; then cd frontend && $(NPM) run dev; else echo "Frontend not yet built (M4)"; fi

demo: ## Start sandbox + backend + frontend (USE_STUBS=1 by default)
	@echo "Starting Redthread demo (USE_STUBS=1)..."
	@USE_STUBS=1 $(MAKE) -j3 sandbox backend frontend

test: ## Run pytest
	$(PYTHON) -m pytest tests/ -v

smoke: ## Run smoke test (USE_STUBS=1, backend must be running)
	USE_STUBS=1 $(PYTHON) scripts/smoke.py

replay: ## Replay the demo run
	@echo "Replaying demo run..."
	$(PYTHON) -c "import asyncio; from backend.replay import stream_replay; \
		async def go(): \
			async for e in stream_replay('demo_run', speed=5): print(e.type, e.payload); \
		asyncio.run(go())"
