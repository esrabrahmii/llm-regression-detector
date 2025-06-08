.PHONY: install run dashboard test lint format clean

PYTHON := python3
VENV := .venv

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e ".[dev,dashboard]"
	@echo ""
	@echo "✓ Installed. Now: cp .env.example .env and add your API keys."

run:
	$(VENV)/bin/lrd run examples/golden_planner.yaml

dashboard:
	$(VENV)/bin/streamlit run src/lrd/dashboard/app.py

test:
	$(VENV)/bin/pytest tests/unit -v

lint:
	$(VENV)/bin/ruff check src/ tests/

format:
	$(VENV)/bin/ruff format src/ tests/

clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache *.egg-info
	rm -f runs.duckdb*
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
