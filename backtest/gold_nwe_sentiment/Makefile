.PHONY: install run grid set-best-nwe clean

install:
	UV_PROJECT_ENVIRONMENT=venv uv sync

run:
	venv/bin/python main.py

grid:
	venv/bin/python run_nwe_grid_search.py

# Lancia la grid search fine e salva la configurazione NWE migliore in best_nwe_params.json:
# 'make run' la userà automaticamente al posto della griglia rada di config.py
set-best-nwe: grid

clean:
	find . -name "__pycache__" -not -path "./venv/*" -exec rm -rf {} +
