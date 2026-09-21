"""Export JSON: serie sentiment allineata alle barre, e trade calcolati dal backtest —
pensati per essere letti una volta dal sito (mai ricalcolati lì), quindi il pulsante nel
grafico web resta istantaneo invece di rilanciare tutta la strategia."""

import json
from datetime import timezone

import pandas as pd


def export_sentiment_json(data: pd.DataFrame, path: str = "gold_sentiment_15m.json") -> str:
    rows = [
        {"time": ts.isoformat(), "score": float(score), "signal": label}
        for ts, score, label in zip(data.index, data["sentiment_score"], data["sentiment_label"])
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    return path


def _epoch(ts: pd.Timestamp) -> int:
    """Stessa convenzione di chart_backend._rows_with_epoch_time nel sito: l'orario
    'wall-clock' della barra viene interpretato come UTC, così il trade cade esattamente
    sulla stessa barra sul grafico anche se la sorgente non è realmente UTC."""
    return int(ts.to_pydatetime().replace(tzinfo=timezone.utc).timestamp())


def export_trades_json(trades: pd.DataFrame, path: str = "trades_nwe.json") -> str:
    rows = [
        {
            "direction": t.direction,
            "entry_time": _epoch(t.entry_time),
            "entry_price": round(float(t.entry_price), 4),
            "exit_time": _epoch(t.exit_time),
            "exit_price": round(float(t.exit_price), 4),
            "stop_price": round(float(t.stop_price), 4),
            "target_price": round(float(t.target_price), 4),
            "pnl": round(float(t.pnl), 2),
            "win": bool(t.win),
        }
        for t in trades.itertuples()
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    return path
