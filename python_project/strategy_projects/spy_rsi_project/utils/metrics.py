"""Metriche di performance."""

import numpy as np


def sharpe_ratio(equity: np.ndarray) -> float:
    """Annualized Sharpe, risk-free = 0."""
    returns = np.diff(equity) / equity[:-1]
    if returns.std() == 0:
        return 0.0
    return (returns.mean() / returns.std()) * np.sqrt(252)


def max_drawdown(equity: np.ndarray) -> float:
    """Max drawdown in percentuale (negativo)."""
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    return drawdown.min()


def total_return(equity: np.ndarray) -> float:
    """Rendimento totale in percentuale."""
    return (equity[-1] - equity[0]) / equity[0]
