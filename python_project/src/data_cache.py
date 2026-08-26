"""SQLite OHLCV cache — stores all intervals, avoids re-downloading data."""

from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ohlcv_cache.db"

_lock = threading.Lock()

# Max yfinance history per interval and corresponding default period to download
INTERVAL_CFG: dict[str, dict] = {
    "1m":  {"yf": "1m",  "max_days": 7,    "dl_period": "7d",  "stale_mins": 5},
    "5m":  {"yf": "5m",  "max_days": 60,   "dl_period": "60d", "stale_mins": 15},
    "15m": {"yf": "15m", "max_days": 60,   "dl_period": "60d", "stale_mins": 30},
    "30m": {"yf": "30m", "max_days": 60,   "dl_period": "60d", "stale_mins": 60},
    "1h":  {"yf": "1h",  "max_days": 730,  "dl_period": "2y",  "stale_mins": 120},
    "4h":  {"yf": "1h",  "max_days": 730,  "dl_period": "2y",  "stale_mins": 240},
    "1d":  {"yf": "1d",  "max_days": 99999,"dl_period": "max", "stale_mins": 720},
    "1wk": {"yf": "1wk", "max_days": 99999,"dl_period": "max", "stale_mins": 1440},
    "1mo": {"yf": "1mo", "max_days": 99999,"dl_period": "max", "stale_mins": 2880},
    "3mo": {"yf": "3mo", "max_days": 99999,"dl_period": "max", "stale_mins": 4320},
}

PERIOD_DAYS: dict[str, int] = {
    "5d": 5, "7d": 7, "1mo": 31, "3mo": 92, "6mo": 183,
    "1y": 365, "2y": 730, "3y": 1095, "5y": 1825,
    "10y": 3650, "max": 99999,
}


@contextmanager
def _conn():
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        yield c
    finally:
        c.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS ohlcv (
                ticker   TEXT NOT NULL,
                interval TEXT NOT NULL,
                date     TEXT NOT NULL,
                open     REAL,
                high     REAL,
                low      REAL,
                close    REAL,
                volume   INTEGER,
                PRIMARY KEY (ticker, interval, date)
            );
            CREATE TABLE IF NOT EXISTS meta (
                ticker   TEXT NOT NULL,
                interval TEXT NOT NULL,
                last_dl  TEXT,
                PRIMARY KEY (ticker, interval)
            );
            CREATE INDEX IF NOT EXISTS idx_tik_int_dt
                ON ohlcv(ticker, interval, date);
        """)
        c.commit()


def _is_stale(ticker: str, interval: str) -> bool:
    cfg = INTERVAL_CFG.get(interval, INTERVAL_CFG["1d"])
    with _conn() as c:
        row = c.execute(
            "SELECT last_dl FROM meta WHERE ticker=? AND interval=?",
            (ticker, interval),
        ).fetchone()
    if not row or not row["last_dl"]:
        return True
    age = datetime.now() - datetime.fromisoformat(row["last_dl"])
    return age.total_seconds() / 60 > cfg["stale_mins"]


def get_cached(ticker: str, interval: str, period: str = "1y") -> list[dict]:
    """Return rows from cache for the requested period (possibly empty)."""
    ticker = ticker.upper()
    days = PERIOD_DAYS.get(period, 365)
    if days >= 99999:
        cutoff = "1900-01-01"
    else:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")
    with _conn() as c:
        rows = c.execute(
            "SELECT date, open, high, low, close, volume FROM ohlcv "
            "WHERE ticker=? AND interval=? AND date>=? ORDER BY date",
            (ticker, interval, cutoff),
        ).fetchall()
    return [dict(r) for r in rows]


def _upsert(ticker: str, interval: str, rows: list[dict]) -> None:
    if not rows:
        return
    with _lock:
        with _conn() as c:
            c.executemany(
                "INSERT OR REPLACE INTO ohlcv "
                "(ticker,interval,date,open,high,low,close,volume) "
                "VALUES(:ticker,:interval,:date,:open,:high,:low,:close,:volume)",
                [{**r, "ticker": ticker.upper(), "interval": interval} for r in rows],
            )
            c.execute(
                "INSERT OR REPLACE INTO meta(ticker,interval,last_dl) VALUES(?,?,?)",
                (ticker.upper(), interval, datetime.now().isoformat()),
            )
            c.commit()


def _df_to_rows(df: pd.DataFrame, interval: str) -> list[dict]:
    """Convert a raw yfinance DataFrame to our row format."""
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
            "low":    None if pd.isna(row.get("low", float("nan"))) else round(float(row["low"]), 4),
            "close":  round(float(c), 4),
            "volume": 0 if pd.isna(row.get("volume", 0)) else int(row["volume"]),
        })
    return rows


def download_and_cache(
    ticker: str, interval: str, period: str | None = None
) -> list[dict]:
    """Download from yfinance, store in DB, and return rows."""
    ticker = ticker.upper()
    cfg = INTERVAL_CFG.get(interval, INTERVAL_CFG["1d"])
    yf_interval = cfg["yf"]
    dl_period = period or cfg["dl_period"]

    try:
        df = yf.download(
            ticker,
            period=dl_period,
            interval=yf_interval,
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty:
            return []

        if interval == "4h":
            df = df.resample("4h").agg(
                {"Open": "first", "High": "max", "Low": "min",
                 "Close": "last", "Volume": "sum"}
            ).dropna(subset=["Close"])

        rows = _df_to_rows(df, interval)
        _upsert(ticker, interval, rows)
        return rows

    except Exception as exc:
        print(f"[cache] download_and_cache {ticker}/{interval}: {exc}")
        return []


def fetch_smart(
    ticker: str, interval: str, period: str = "1y"
) -> list[dict]:
    """
    Return OHLCV rows for the given ticker/interval/period.
    Uses cache when fresh; re-downloads when stale.
    """
    ticker = ticker.upper()
    stale = _is_stale(ticker, interval)

    if not stale:
        rows = get_cached(ticker, interval, period)
        if rows:
            return rows

    # Download fresh data
    rows = download_and_cache(ticker, interval, period)
    if rows:
        # Filter by requested period
        return get_cached(ticker, interval, period) or rows

    # Fallback: return whatever is in cache even if stale
    return get_cached(ticker, interval, period)


def background_download_all(ticker: str) -> None:
    """Download all standard intervals for a ticker in a background thread."""

    def _worker():
        intervals = ["1d", "1wk", "1mo", "1h", "4h", "5m", "15m", "30m", "1m"]
        for iv in intervals:
            try:
                if _is_stale(ticker, iv):
                    download_and_cache(ticker, iv)
                time.sleep(0.8)          # gentle rate-limiting
            except Exception as exc:
                print(f"[cache] bg {ticker}/{iv}: {exc}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def cache_stats(ticker: str) -> dict:
    """Return cache coverage info for a ticker."""
    ticker = ticker.upper()
    with _conn() as c:
        rows = c.execute(
            "SELECT interval, COUNT(*) as cnt, MIN(date) as first_dt, MAX(date) as last_dt "
            "FROM ohlcv WHERE ticker=? GROUP BY interval",
            (ticker,),
        ).fetchall()
        meta = c.execute(
            "SELECT interval, last_dl FROM meta WHERE ticker=?", (ticker,)
        ).fetchall()
    meta_dict = {r["interval"]: r["last_dl"] for r in meta}
    return {
        r["interval"]: {
            "count": r["cnt"],
            "from": r["first_dt"],
            "to": r["last_dt"],
            "last_dl": meta_dict.get(r["interval"]),
        }
        for r in rows
    }


# Auto-init on import
try:
    init_db()
except Exception as _e:
    print(f"[cache] init_db warning: {_e}")
