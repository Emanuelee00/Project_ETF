"""Export JSON della serie sentiment (score + etichetta) allineata alle barre usate dalla strategia."""

import json

import pandas as pd


def export_sentiment_json(data: pd.DataFrame, path: str = "gold_sentiment_15m.json") -> str:
    rows = [
        {"time": ts.isoformat(), "score": float(score), "signal": label}
        for ts, score, label in zip(data.index, data["sentiment_score"], data["sentiment_label"])
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    return path
