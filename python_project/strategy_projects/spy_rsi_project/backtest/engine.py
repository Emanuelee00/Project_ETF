"""Simulazione equity curve."""

import pandas as pd


def backtest(data, capital: float, risk: float):
    """Ritorna equity curve giornaliera."""
    equity = capital
    position = 0.0
    equity_curve = []
    prices = data["Close"].values
    signals = data["signal"].values

    for price, sig in zip(prices, signals):
        if sig == 1 and position == 0:
            position = equity * (risk / 100) / price
            equity -= equity * (risk / 100)
        elif sig == 0 and position > 0:
            equity += position * price
            position = 0.0
        equity_curve.append(equity + position * price)

    result = data.copy()
    result["equity"] = equity_curve
    return result
