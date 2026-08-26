# 📊 ETF Portfolio Analyzer

A Python toolkit for analyzing and backtesting a multi-asset ETF/stock portfolio, with two ways to use it:

* a **web app** (FastAPI + interactive charts) for exploring tickers, running strategy backtests and reading news sentiment
* a **CLI pipeline** that turns a spreadsheet of ISINs/tickers into a full Excel analytics report

---

## 🧱 Project Structure

```
python_project/
├── src/
│   ├── server.py            # FastAPI app (web UI + API)
│   ├── chart_backend.py     # OHLCV chart data (cache-first, yfinance/stooq fallback)
│   ├── data_cache.py        # SQLite OHLCV cache
│   ├── main.py               # CLI pipeline entry point
│   ├── analytics.py          # Performance metrics
│   ├── risk_metrics.py       # Risk metrics
│   ├── optimization.py       # Monte Carlo portfolio optimization
│   ├── seasonality.py        # Multi-horizon stability analysis
│   ├── excel_export.py       # Excel report generation
│   ├── country.py            # Ticker → country detection
│   ├── auto_mapping.py       # ISIN → ticker mapping helper
│   └── static/                # Web frontend (SPA + chart indicators)
├── strategy_projects/         # Standalone strategy research scripts
│   ├── multi_asset_moving_average_cross/
│   └── spy_rsi_project/
├── data/                      # Input spreadsheet, ISIN/ticker mapping, OHLCV cache
├── output/                     # Generated Excel reports
├── Dockerfile / docker-compose.yml
└── pyproject.toml / uv.lock
```

---

## ⚙️ Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/):

```bash
make install
```

This creates `venv/` and installs everything from `pyproject.toml` / `uv.lock` (also for the two strategy sub-projects).

---

## 🚀 Running

### Web app

```bash
make run
# or: venv/bin/python start_web.py
```

Opens on `http://localhost:8000` (falls back to 8001/8002 if busy). Or with Docker:

```bash
docker compose up --build
```

**What's in it:**

* **Search** — global ticker/ISIN search, or upload a portfolio spreadsheet for a full metrics table
* **Chart** — candlestick chart (any yfinance ticker, intervals from 1m to 3mo) with SMA, EMA, RSI, Nadaraya-Watson envelope, pivot points and volume profile
* **Strategy** — backtest and optimize two engines against any ticker:
  * *MA Crossover* with optional RSI/trend filters
  * *RSI Mean-Reversion* (long while RSI < oversold, flat once RSI > overbought)

  Both support a parameter grid search ("Trova configurazioni migliori") ranked by a trade-count-aware composite score.
* **News** — recent headlines per ticker with a simple keyword-based sentiment score and buy/sell/hold signal

### CLI pipeline (Excel report)

```bash
make main
```

Reads `data/himalaya.xlsx` (or the configured input file), resolves ISINs to tickers via `data/isin_ticker_mapping.csv`, downloads prices, computes metrics, and writes a full Excel report to `output/`.

---

## 🔄 CLI Pipeline Flow

```
Excel (ISIN)
    ↓
ISIN → Ticker mapping
    ↓
Market data download (Yahoo Finance)
    ↓
Performance metrics
    ↓
Risk metrics
    ↓
Portfolio optimization
    ↓
Multi-horizon stability analysis
    ↓
Excel report
```

---

## 📈 Analytics

### Performance (`analytics.py`)

Current Price · Perf 1Y/3Y/5Y · CAGR 3Y/5Y · Avg Daily Return · Annual Return · Skewness · Kurtosis · Correlation & Covariance vs Benchmark

### Risk (`risk_metrics.py`)

* Volatility (annualized): `σ_annual = std(daily_returns) * √252`
* Sharpe Ratio: `(Annual Return − Risk Free Rate) / Annual Volatility`
* Beta: `Cov(asset, benchmark) / Var(benchmark)`
* Max Drawdown: `(Cumulative − RollingMax) / RollingMax`

### Portfolio Optimization (`optimization.py`)

Monte Carlo simulation over random portfolio weights → Max Sharpe portfolio, Min Volatility portfolio, correlation matrix.

### Multi-Horizon Stability (`seasonality.py`)

Rolling cumulative returns pivoted by year, correlated across years, averaged over the upper triangle:

| Value   | Meaning          |
| ------- | ---------------- |
| > 0.6   | Strong stability |
| 0.3–0.6 | Moderate         |
| 0–0.3   | Weak             |
| < 0     | Unstable         |

---

## 📊 Excel Report

Dashboard (asset count, avg Sharpe/volatility/CAGR/drawdown) · Metrics table · Correlation heatmap · Max Sharpe & Min Volatility portfolio weights · Seasonality heatmap.

---

## 🌍 Country Detection

Ticker suffix → country: `.L` UK · `.PA` France · `.DE`/`.F`/`.MU` Germany · `.MI` Italy · `.SW` Switzerland · `.AS` Netherlands · `.SI` Singapore.

Default benchmark: **IWDA.AS**.

---

## ⚠️ Known Constraints

* Yahoo Finance limits intraday history: 1m ≈ 7 days, 5m/15m/30m ≈ 60 days, 1h/4h ≈ 2 years
* Horizons beyond available data length return NaN
* Optimization may slow down with >100 assets

---

## 👨‍💻 Author

Emanuele Ielmini
