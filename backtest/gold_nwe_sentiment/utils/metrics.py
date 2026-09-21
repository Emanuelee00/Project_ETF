"""Metriche di performance (adattate a barre intraday, non solo giornaliere)."""

import numpy as np


def sharpe_ratio(equity: np.ndarray, periods_per_year: float = 252) -> float:
    """Sharpe annualizzato, risk-free = 0. Su barre intraday passare periods_per_year
    coerente (es. barre da 15 min: bar/giorno osservate * 252 giorni di trading)."""
    returns = np.diff(equity) / equity[:-1]
    if returns.std() == 0:
        return 0.0
    return (returns.mean() / returns.std()) * np.sqrt(periods_per_year)


def max_drawdown(equity: np.ndarray) -> float:
    """Max drawdown in percentuale (negativo)."""
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    return drawdown.min()


def total_return(equity: np.ndarray) -> float:
    """Rendimento totale in percentuale."""
    return (equity[-1] - equity[0]) / equity[0]
