"""Sentiment giornaliero sull'oro (BUY/SELL) sovrapposto al grafico prezzi.

Legge lo storico calcolato dal progetto gold_agent (../gold_agent/gold_sentiment.db,
alimentato dal ciclo LangGraph + LLM locale) e lo allinea alle barre OHLCV già servite
da /api/chart, ripetendo il segnale del giorno su ogni barra intraday di quel giorno.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from chart_backend import get_chart_payload

GOLD_DB_PATH = Path(__file__).resolve().parent.parent.parent / "gold_agent" / "gold_sentiment.db"

# Ticker per cui ha senso mostrare il sentiment sull'oro (allineati a gold_agent/config.py)
GOLD_TICKERS = {"GC=F", "GLD", "XAUUSD=X", "GOLD", "XAU"}


def _daily_signals() -> dict[str, dict]:
    if not GOLD_DB_PATH.exists():
        return {}
    try:
        conn = sqlite3.connect(f"file:{GOLD_DB_PATH}?mode=ro", uri=True)
        rows = conn.execute("SELECT fetched_on, signal, overall_score FROM daily_summary").fetchall()
        conn.close()
    except Exception:
        return {}
    return {r[0]: {"signal": r[1], "score": r[2]} for r in rows}


def _bar_date(value) -> str:
    """Le barre intraday hanno 'date' come timestamp UNIX, quelle giornaliere+ come stringa YYYY-MM-DD."""
    if isinstance(value, int):
        return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%Y-%m-%d")
    return str(value)[:10]


def get_gold_sentiment_markers(ticker: str, period: str, interval: str) -> list[dict]:
    """Un marker per ogni barra del giorno in cui gold_agent ha salvato un segnale BUY/SELL."""
    if ticker.strip().upper() not in GOLD_TICKERS:
        return []

    signals = _daily_signals()
    if not signals:
        return []

    payload = get_chart_payload(ticker, period, interval)
    markers = []
    for row in payload["rows"]:
        day = _bar_date(row["date"])
        sig = signals.get(day)
        if not sig or sig["signal"] == "HOLD":
            continue
        markers.append({"time": row["date"], "signal": sig["signal"], "score": sig["score"]})

    return markers
