.PHONY: install run backfill clean

DAYS ?= 365

install:
	UV_PROJECT_ENVIRONMENT=venv uv sync

run:
	venv/bin/python main.py

# Backfill storico da GDELT (gratis, nessuna API key): DAYS=90 make backfill per un periodo più corto
backfill:
	venv/bin/python backfill_gold_history.py --days $(DAYS)

clean:
	find . -name "__pycache__" -not -path "./venv/*" -exec rm -rf {} +
