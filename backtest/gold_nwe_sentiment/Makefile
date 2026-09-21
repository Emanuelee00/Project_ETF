.PHONY: install run grid set-best-nwe monitor clean

install:
	UV_PROJECT_ENVIRONMENT=venv uv sync

run:
	venv/bin/python main.py

grid:
	venv/bin/python run_nwe_grid_search.py

# Lancia la grid search fine e salva la configurazione NWE migliore in best_nwe_params.json:
# 'make run' la userà automaticamente al posto della griglia rada di config.py
set-best-nwe: grid

# Loop continuo: controlla ogni minuto se scatta un nuovo trade e avvisa su Telegram
# (richiede 'make run' già lanciato almeno una volta, e TELEGRAM_BOT_TOKEN/CHAT_ID in .env)
monitor:
	venv/bin/python monitor.py

clean:
	find . -name "__pycache__" -not -path "./venv/*" -exec rm -rf {} +
