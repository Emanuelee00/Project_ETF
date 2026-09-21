"""Legge i trade già calcolati da backtest/gold_nwe_sentiment/main.py (trades_nwe.json).

Nessun ricalcolo qui: il backtest gira una volta con `make gold-nwe` e scrive il JSON,
questo modulo si limita a leggerlo — così il pulsante nel grafico web resta istantaneo.
"""

from __future__ import annotations

import json
from pathlib import Path

TRADES_PATH = Path(__file__).resolve().parent.parent.parent / "backtest" / "gold_nwe_sentiment" / "trades_nwe.json"


def get_nwe_trades() -> list[dict]:
    if not TRADES_PATH.exists():
        return []
    try:
        return json.loads(TRADES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
