.PHONY: install run main multi-asset spy clean

install:
	UV_PROJECT_ENVIRONMENT=venv uv sync
	cd strategy_projects/multi_asset_moving_average_cross && UV_PROJECT_ENVIRONMENT=venv uv sync
	cd strategy_projects/spy_rsi_project && UV_PROJECT_ENVIRONMENT=venv uv sync

run:
	venv/bin/python start_web.py

main:
	venv/bin/python src/main.py

multi-asset:
	cd strategy_projects/multi_asset_moving_average_cross && venv/bin/python main.py

spy:
	cd strategy_projects/spy_rsi_project && venv/bin/python main.py

clean:
	find . -name "__pycache__" -not -path "./venv/*" -not -path "./strategy_projects/multi_asset_moving_average_cross/venv/*" -not -path "./strategy_projects/spy_rsi_project/venv/*" -exec rm -rf {} +
