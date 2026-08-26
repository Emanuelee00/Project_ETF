"""Chart data API — cache-first, multi-source fallback."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

_INTRADAY_INTERVALS = {"1m", "5m", "15m", "30m", "1h", "4h"}

# ── interval → (yf_interval, default_period) ──────────────────────────────────
INTERVAL_MAP: dict[str, tuple[str, str]] = {
    "1m":  ("1m",  "5d"),
    "5m":  ("5m",  "30d"),
    "15m": ("15m", "30d"),
    "30m": ("30m", "30d"),
    "1h":  ("1h",  "90d"),
    "4h":  ("1h",  "180d"),
    "1d":  ("1d",  "1y"),
    "1wk": ("1wk", "5y"),
    "1mo": ("1mo", "10y"),
    "3mo": ("3mo", "max"),
}

_PERIOD_DAYS = {
    "5d": 5, "7d": 7, "1mo": 31, "3mo": 92, "6mo": 183,
    "1y": 365, "2y": 730, "3y": 1095, "5y": 1825,
    "10y": 3650, "max": float("inf"),
}
_INTRADAY_MAX_DAYS = {"1m": 7, "5m": 60, "15m": 60, "30m": 60, "1h": 730, "4h": 730}


def _safe_period(interval: str, period: str) -> str:
    """Keep intraday requests within Yahoo Finance's available history."""
    max_days = _INTRADAY_MAX_DAYS.get(interval)
    if max_days is None or _PERIOD_DAYS.get(period, float("inf")) <= max_days:
        return period
    return INTERVAL_MAP[interval][1]


def _get_name_and_isin(ticker: str) -> tuple[str, str]:
    try:
        info = yf.Ticker(ticker).info
        name = info.get("longName") or info.get("shortName") or ticker
        isin = info.get("isin", "")
        return name, isin
    except Exception:
        return ticker, ""


def _fetch_yfinance(ticker: str, period: str, yf_interval: str) -> pd.DataFrame:
    LEGACY = {
        "1mo": "1mo", "3mo": "3mo", "6mo": "6mo",
        "1y": "1y", "2y": "2y", "5y": "5y", "10y": "10y", "max": "max",
    }
    use_period = LEGACY.get(period, period) or "1y"
    df = yf.download(
        ticker, period=use_period, interval=yf_interval,
        progress=False, auto_adjust=False, threads=False,
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _stooq_fallback(ticker: str) -> pd.DataFrame:
    import requests
    try:
        url = f"https://stooq.com/q/d/l/?s={ticker.lower()}&i=d"
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and "Date" in r.text:
            from io import StringIO
            df = pd.read_csv(StringIO(r.text))
            df.columns = [c.capitalize() for c in df.columns]
            df["Date"] = pd.to_datetime(df["Date"])
            return df.set_index("Date").sort_index()
    except Exception:
        pass
    return pd.DataFrame()


def _rows_with_epoch_time(rows: list[dict]) -> list[dict]:
    """Turn the 'YYYY-MM-DDTHH:MM' wall-clock string used for intraday rows into a
    UNIX timestamp (seconds). lightweight-charts renders intraday series using a
    numeric UTCTimestamp — handing it that string instead throws inside the
    library once time-of-day resolution is involved. Interpreting the wall-clock
    string as UTC keeps the displayed hour/minute unchanged (the library shows
    UTCTimestamp values in UTC), it just moves the parsing our side."""
    for r in rows:
        r["date"] = int(
            datetime.strptime(r["date"], "%Y-%m-%dT%H:%M")
            .replace(tzinfo=timezone.utc)
            .timestamp()
        )
    return rows


def _df_to_rows(df: pd.DataFrame, interval: str) -> list[dict]:
    df = df.reset_index()
    df.columns = [str(c).lower() for c in df.columns]
    date_col = next(
        (x for x in df.columns if x in ("date", "datetime")), df.columns[0]
    )
    df[date_col] = pd.to_datetime(df[date_col])
    if interval in ("1m", "5m", "15m", "30m", "1h", "4h"):
        df["_ds"] = df[date_col].dt.strftime("%Y-%m-%dT%H:%M")
    else:
        df["_ds"] = df[date_col].dt.strftime("%Y-%m-%d")
    rows = []
    for _, row in df.iterrows():
        c = row.get("close")
        if pd.isna(c):
            continue
        rows.append({
            "date":   row["_ds"],
            "open":   None if pd.isna(row.get("open", float("nan"))) else round(float(row["open"]), 4),
            "high":   None if pd.isna(row.get("high", float("nan"))) else round(float(row["high"]), 4),
            "low":    None if pd.isna(row.get("low", float("nan")))  else round(float(row["low"]), 4),
            "close":  round(float(c), 4),
            "volume": 0 if pd.isna(row.get("volume", 0)) else int(row["volume"]),
        })
    return rows


def get_chart_payload(
    ticker: str, period: str = "1y", interval: str = "1d"
) -> dict:
    """Fetch OHLCV data — cache-first with automatic background refresh."""
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Ticker is required.")

    _, default_period = INTERVAL_MAP.get(interval, INTERVAL_MAP["1d"])
    use_period = _safe_period(interval, period or default_period)

    # ── Try cache first ──────────────────────────────────────────────────────
    cached_flag = False
    rows: list[dict] = []
    try:
        from data_cache import fetch_smart, background_download_all
        rows = fetch_smart(ticker, interval, use_period)
        if rows:
            cached_flag = True
            # Trigger background download of ALL intervals (fire-and-forget)
            background_download_all(ticker)
    except Exception:
        pass

    # ── Fall back to direct download if cache missed ─────────────────────────
    if not rows:
        yf_interval, _ = INTERVAL_MAP.get(interval, INTERVAL_MAP["1d"])
        df: pd.DataFrame = pd.DataFrame()
        try:
            df = _fetch_yfinance(ticker, use_period, yf_interval)
        except Exception:
            pass

        if df.empty and interval == "1d":
            df = _stooq_fallback(ticker)

        if df.empty:
            raise FileNotFoundError(f"No data found for '{ticker}'.")

        if interval == "4h" and not df.empty:
            df = df.resample("4h").agg(
                {"Open": "first", "High": "max",
                 "Low": "min", "Close": "last", "Volume": "sum"}
            ).dropna(subset=["Close"])

        rows = _df_to_rows(df, interval)
        # Store in cache for next time
        try:
            from data_cache import _upsert
            _upsert(ticker, interval, rows)
        except Exception:
            pass

    if not rows:
        raise FileNotFoundError(f"No usable rows for '{ticker}'.")

    if interval in _INTRADAY_INTERVALS:
        rows = _rows_with_epoch_time(rows)

    name, isin = _get_name_and_isin(ticker)
    return {
        "ticker":   ticker,
        "name":     name,
        "isin":     isin,
        "period":   use_period,
        "interval": interval,
        "rows":     rows,
        "cached":   cached_flag,
    }
