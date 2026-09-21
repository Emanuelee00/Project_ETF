"""Prezzi dell'oro dalla cache SQLite condivisa con python_project (ohlcv_cache.db, la
stessa usata dal server web) e sentiment giornaliero salvato da gold_agent.

La cache fa INSERT OR REPLACE per (ticker, interval, date): le barre più vecchie della
finestra scaricabile da Yahoo Finance (60 giorni per il 15m) restano comunque in archivio
dalle run precedenti, quindi lo storico REALE cresce ad ogni run invece di restare fisso a
60 giorni — non serve un backfill separato, basta lanciare il progetto (o usare il grafico
web) regolarmente.
"""

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

import config

OHLCV_DB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "python_project" / "data" / "ohlcv_cache.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ohlcv (
    ticker TEXT NOT NULL, interval TEXT NOT NULL, date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume INTEGER,
    PRIMARY KEY (ticker, interval, date)
);
CREATE TABLE IF NOT EXISTS meta (
    ticker TEXT NOT NULL, interval TEXT NOT NULL, last_dl TEXT,
    PRIMARY KEY (ticker, interval)
);
"""


def _connect() -> sqlite3.Connection:
    OHLCV_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(OHLCV_DB_PATH), timeout=10)
    conn.executescript(_SCHEMA)
    return conn


def _fetch_fresh(ticker: str, interval: str, period: str) -> pd.DataFrame:
    df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False, threads=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["Close"])


def _upsert(conn: sqlite3.Connection, ticker: str, interval: str, df: pd.DataFrame) -> None:
    df = df.reset_index()
    df.columns = [str(c).lower() for c in df.columns]
    date_col = next((c for c in df.columns if c in ("date", "datetime")), df.columns[0])
    df["_ds"] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%dT%H:%M")

    rows = [
        {
            "ticker": ticker.upper(), "interval": interval, "date": r["_ds"],
            "open": None if pd.isna(r.get("open")) else float(r["open"]),
            "high": None if pd.isna(r.get("high")) else float(r["high"]),
            "low": None if pd.isna(r.get("low")) else float(r["low"]),
            "close": float(r["close"]),
            "volume": 0 if pd.isna(r.get("volume", 0)) else int(r["volume"]),
        }
        for _, r in df.iterrows() if not pd.isna(r.get("close"))
    ]
    if not rows:
        return

    conn.executemany(
        "INSERT OR REPLACE INTO ohlcv (ticker,interval,date,open,high,low,close,volume) "
        "VALUES (:ticker,:interval,:date,:open,:high,:low,:close,:volume)",
        rows,
    )
    conn.execute(
        # naive, senza timezone: data_cache.py (python_project) confronta con datetime.now()
        # anch'esso naive — un timestamp aware qui rompe _is_stale() lì con un TypeError
        "INSERT OR REPLACE INTO meta (ticker,interval,last_dl) VALUES (?,?,?)",
        (ticker.upper(), interval, datetime.now().isoformat()),
    )
    conn.commit()


def load_price_data(ticker: str = None, interval: str = None, period: str = None, refresh: bool = True) -> pd.DataFrame:
    """Storico OHLC accumulato in cache. Se refresh=True, scarica prima l'ultima finestra
    disponibile da Yahoo e la unisce alla cache (le barre nuove si aggiungono, quelle già
    presenti restano) — così ogni run allunga lo storico invece di ripartire da 60 giorni."""
    ticker = (ticker or config.TICKER).upper()
    interval = interval or config.INTERVAL
    period = period or config.PERIOD

    with closing(_connect()) as conn:
        if refresh:
            try:
                fresh = _fetch_fresh(ticker, interval, period)
                if not fresh.empty:
                    _upsert(conn, ticker, interval, fresh)
            except Exception as exc:
                print(f"[data_loader] fetch/refresh fallito, uso solo la cache: {exc}")

        rows = conn.execute(
            "SELECT date, open, high, low, close, volume FROM ohlcv "
            "WHERE ticker=? AND interval=? ORDER BY date",
            (ticker, interval),
        ).fetchall()

    if not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    df = pd.DataFrame(rows, columns=["date", "Open", "High", "Low", "Close", "Volume"])
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def load_daily_sentiment(db_path: str = None) -> dict:
    """{data ISO: {'signal': 'BUY'|'SELL'|'HOLD', 'score': float}} dal ciclo LangGraph di gold_agent."""
    path = Path(__file__).resolve().parent.parent / (db_path or config.GOLD_SENTIMENT_DB)
    if not path.exists():
        return {}

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    rows = conn.execute("SELECT fetched_on, signal, overall_score FROM daily_summary").fetchall()
    conn.close()
    return {r[0]: {"signal": r[1], "score": r[2]} for r in rows}
