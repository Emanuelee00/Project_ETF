# Project History

Chronological log of the work done to bring the ETF Analyzer web app online, fix its
bugs, and clean up the repository.

## Web app: candlestick chart fix

The chart view showed "Errore: Cannot read properties of null (reading 'value')"
instead of candles. Root cause: the indicator sidebar had been refactored to use
dynamic `data-indicator-id`/`data-indicator-param` inputs, but `renderChart()` and
`_setupRsiChart()` still read indicator parameters from the old fixed element ids
(`per-sma`, `per-ema`, `per-rsi`, `per-nwh`, `per-nwm`), which no longer existed in
the DOM. Fixed by reading parameters through the existing `_indicatorParam()`
helper instead, and removed the now-dead listener registered on those old ids.

## News section review

Reviewed the News view (standalone page and the panel embedded in the chart view)
end to end — search, sentiment scoring, buy/sell/hold signal. No issues found.

## Repository cleanup and initial commit

Committed the full web app (`server.py`, `chart_backend.py`, `data_cache.py`,
`static/`) along with the candlestick fix. Removed the `env/` virtualenv that had
been committed by mistake (thousands of files), superseded by the gitignored
`venv/`.

## RSI Mean-Reversion strategy

Ported the standalone RSI mean-reversion strategy (`strategy_projects/spy_rsi_project`)
into the web app's Strategy tab, alongside the existing MA Crossover engine:

- Strategy-type toggle (MA Crossover / RSI Mean-Rev) in the sidebar, with RSI
  period/oversold/overbought inputs replacing the MA fields when selected
- A new "SPY · RSI Mean-Reversion" preset
- Backend support for both `/api/strategy/backtest` and `/api/strategy/optimize`
  (`_prepare_rsi_backtest_frame` / `_simulate_rsi_trades`), reusing the existing
  equity-curve/trades/stats response shape so no frontend rendering changes were
  needed for the new engine

Also updated the `Dockerfile` to install dependencies via `uv` (`pyproject.toml`/
`uv.lock`) instead of the removed `requirements.txt`.

## Optimizer score fix

The RSI strategy's "Trova configurazioni migliori" was surfacing configurations
validated on only 1-2 trades as the "best" result — a lucky, statistically
insignificant sample with a tiny drawdown could easily outscore a config with a
dozen trades and a strong win rate. Added `_composite_score()`, which damps the
raw score by `min(num_trades / 10, 1)` so a configuration needs roughly 10+ trades
to reach full confidence. Applied to both the MA-crossover and RSI optimizers,
which share the same scoring formula.

## Intraday candlestick fix (1m-4h)

Sub-daily chart intervals (1m/5m/15m/30m/1h/4h) were throwing internal
"Value is null" errors inside the charting library on every render, because the
backend sent intraday rows with `date` as a `"YYYY-MM-DDTHH:MM"` string —
lightweight-charts needs a numeric UNIX timestamp to render time-of-day
resolution. `get_chart_payload()` now converts intraday rows to epoch seconds
right before returning the API response (the SQLite cache itself is untouched,
still string-keyed); the wall-clock string is parsed as UTC so the displayed
hour/minute doesn't shift. Updated the two frontend spots that assumed a date
string: `pivots.js`'s session-day grouping and the chart tooltip header.

## Publishing to GitHub

Pushed the repository to `github.com:Emanuelee00/Project_ETF.git`. Diagnosed and
fixed SSH authentication (the existing key wasn't authorized for the account;
generated and registered a new dedicated key). Rewrote the pushed commits to
drop the `Co-Authored-By` trailers, then force-pushed — safe since the repo had
just been created and no one else had based work on it yet.

## README refresh

Replaced the outdated README (which only described the old CLI/Excel pipeline,
`env/`, `requirements.txt`) with one covering the current project: the web app
(chart, strategies, news), the CLI pipeline, and the `uv`-based setup.
