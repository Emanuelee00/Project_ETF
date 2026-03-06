"""Robust risk metrics calculations."""

import numpy as np
import pandas as pd

RISK_FREE_RATE = 0.02
TRADING_DAYS = 252
MIN_OBS = 60


def compute_volatility(returns: pd.DataFrame) -> pd.Series:
    """Compute annualized volatility using available data."""
    vol = returns.std() * np.sqrt(TRADING_DAYS)
    return vol


def compute_sharpe(returns: pd.DataFrame) -> pd.Series:
    """Compute Sharpe ratio using available data."""
    mean_daily = returns.mean()
    vol_daily = returns.std()

    sharpe = ((mean_daily * TRADING_DAYS) - RISK_FREE_RATE) / (vol_daily * np.sqrt(TRADING_DAYS))
    sharpe = sharpe.replace([np.inf, -np.inf], np.nan)

    return sharpe


def compute_beta(returns: pd.DataFrame, benchmark: str) -> pd.Series:
    """Compute beta vs benchmark using aligned data."""

    if benchmark not in returns.columns:
        raise ValueError("Benchmark not found.")

    benchmark_returns = returns[benchmark]
    betas = {}

    for col in returns.columns:
        aligned = pd.concat([returns[col], benchmark_returns], axis=1).dropna()

        if len(aligned) < MIN_OBS:
            betas[col] = np.nan
            continue

        cov = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])[0, 1]
        var = np.var(aligned.iloc[:, 1])

        betas[col] = cov / var if var != 0 else np.nan

    return pd.Series(betas)


def compute_max_drawdown(returns: pd.DataFrame) -> pd.Series:
    """Compute max drawdown on full available period."""

    cumulative = (1 + returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max

    return drawdown.min()
