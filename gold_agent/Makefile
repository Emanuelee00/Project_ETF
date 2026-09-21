.PHONY: install run clean

install:
	UV_PROJECT_ENVIRONMENT=venv uv sync

run:
	venv/bin/python main.py

clean:
	find . -name "__pycache__" -not -path "./venv/*" -exec rm -rf {} +
