"""Strategia RSI mean-reversion."""

import pandas as pd


def _calc_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def rsi_strategy(data, period: int, oversold: int, overbought: int):
    """Aggiunge colonne 'rsi' e 'signal' al DataFrame."""
    result = data.copy()
    result["rsi"] = _calc_rsi(result["Close"], period)
    signal = pd.Series(float("nan"), index=result.index)
    signal[result["rsi"] < oversold] = 1
    signal[result["rsi"] > overbought] = 0
    result["signal"] = signal.ffill().fillna(0)
    return result
