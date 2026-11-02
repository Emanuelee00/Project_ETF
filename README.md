# Project_ETF

Three small, independent Python projects around a multi-asset ETF and stock portfolio.

| Folder | What it is |
|---|---|
| [`python_project/`](python_project) | ETF Portfolio Analyzer: a FastAPI web app with interactive charts and a command-line pipeline that turns a spreadsheet of ISINs and tickers into an Excel analytics report (performance, risk, Monte Carlo optimisation, seasonality). It has its own README. |
| [`gold_agent/`](gold_agent) | An agent that reads gold market news and scores sentiment with a local LLM, saving one row per day to SQLite. Meant to run once a day (for example from cron). |
| [`backtest/`](backtest) | Backtests of the sentiment signal. |

Each folder has its own `pyproject.toml` and is managed with `uv`.

This is a personal learning project, not investment advice.
