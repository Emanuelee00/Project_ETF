.PHONY: install run main multi-asset spy gold gold-nwe gold-nwe-grid gold-nwe-set-best news clean

MARKET ?= oro

install:
	UV_PROJECT_ENVIRONMENT=venv uv sync
	cd strategy_projects/multi_asset_moving_average_cross && UV_PROJECT_ENVIRONMENT=venv uv sync
	cd strategy_projects/spy_rsi_project && UV_PROJECT_ENVIRONMENT=venv uv sync
	cd ../gold_agent && UV_PROJECT_ENVIRONMENT=venv uv sync
	cd ../backtest/gold_nwe_sentiment && UV_PROJECT_ENVIRONMENT=venv uv sync

run:
	venv/bin/python start_web.py

main:
	venv/bin/python src/main.py

multi-asset:
	cd strategy_projects/multi_asset_moving_average_cross && venv/bin/python main.py

spy:
	cd strategy_projects/spy_rsi_project && venv/bin/python main.py

gold:
	cd ../gold_agent && venv/bin/python main.py

news:
	cd ../gold_agent && venv/bin/python main.py --market $(MARKET)

gold-nwe:
	cd ../backtest/gold_nwe_sentiment && venv/bin/python main.py

gold-nwe-grid:
	cd ../backtest/gold_nwe_sentiment && venv/bin/python run_nwe_grid_search.py

gold-nwe-set-best: gold-nwe-grid

clean:
	find . -name "__pycache__" -not -path "./venv/*" -not -path "./strategy_projects/multi_asset_moving_average_cross/venv/*" -not -path "./strategy_projects/spy_rsi_project/venv/*" -exec rm -rf {} +
