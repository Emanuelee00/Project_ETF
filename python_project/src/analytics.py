"""Advanced portfolio analytics (production-grade robust version)."""

import numpy as np
import pandas as pd
import yfinance as yf

RISK_FREE_RATE = 0.02
TRADING_DAYS = 252


# ---------------------------------------------------
# PRICE DOWNLOAD
# ---------------------------------------------------

def fetch_prices(tickers: list[str], period: str = "5y") -> pd.DataFrame:
    """Download price data robustly."""

    data = yf.download(
        tickers,
        period=period,
        progress=False,
        threads=True
    )

    # Multi-ticker case
    if isinstance(data.columns, pd.MultiIndex):

        if "Adj Close" in data.columns.levels[0]:
            prices = data["Adj Close"]
        elif "Close" in data.columns.levels[0]:
            prices = data["Close"]
        else:
            raise ValueError("No usable price column found.")

    # Single ticker case
    else:

        if "Adj Close" in data.columns:
            prices = data["Adj Close"].to_frame(name=tickers[0])
        elif "Close" in data.columns:
            prices = data["Close"].to_frame(name=tickers[0])
        else:
            raise ValueError("No usable price column found.")

    # Remove assets completely empty
    prices = prices.dropna(axis=1, how="all")

    return prices


# ---------------------------------------------------
# RETURNS
# ---------------------------------------------------

def compute_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute daily returns safely."""
    returns = prices.pct_change()
    return returns.dropna(how="all")


# ---------------------------------------------------
# PERFORMANCE
# ---------------------------------------------------

def compute_performance(prices: pd.DataFrame, years: int) -> pd.Series:
    """Total return over N years."""
    period_days = years * TRADING_DAYS

    result = pd.Series(index=prices.columns, dtype=float)

    for col in prices.columns:
        series = prices[col].dropna()

        if len(series) < period_days:
            result[col] = np.nan
        else:
            period_prices = series.tail(period_days)
            result[col] = period_prices.iloc[-1] / period_prices.iloc[0] - 1

    return result


def compute_cagr(prices: pd.DataFrame, years: int) -> pd.Series:
    """CAGR over N years."""
    period_days = years * TRADING_DAYS

    result = pd.Series(index=prices.columns, dtype=float)

    for col in prices.columns:
        series = prices[col].dropna()

        if len(series) < period_days:
            result[col] = np.nan
        else:
            period_prices = series.tail(period_days)
            result[col] = (period_prices.iloc[-1] / period_prices.iloc[0]) ** (1 / years) - 1

    return result


# ---------------------------------------------------
# METRICS
# ---------------------------------------------------

def compute_metrics(prices: pd.DataFrame, benchmark: str):

    returns = compute_returns(prices)

    # ------------------------------------------
    # PERFORMANCE
    # ------------------------------------------

    perf_1y = compute_performance(prices, 1)
    perf_3y = compute_performance(prices, 3)
    perf_5y = compute_performance(prices, 5)

    cagr_3y = compute_cagr(prices, 3)
    cagr_5y = compute_cagr(prices, 5)

    # ------------------------------------------
    # DISTRIBUTION STATS
    # ------------------------------------------

    avg_daily_return = returns.mean(skipna=True)
    annual_return = avg_daily_return * TRADING_DAYS
    skewness = returns.skew(skipna=True)
    kurtosis = returns.kurtosis(skipna=True)

    # ------------------------------------------
    # CORRELATION & COVARIANCE (ROBUST)
    # ------------------------------------------

    correlation_vs_bench = pd.Series(index=returns.columns, dtype=float)
    covariance_vs_bench = pd.Series(index=returns.columns, dtype=float)

    if benchmark not in returns.columns:
        raise ValueError("Benchmark not found in returns.")

    for col in returns.columns:

        if col == benchmark:
            correlation_vs_bench[col] = 1.0
            covariance_vs_bench[col] = returns[benchmark].var()
            continue

        aligned = pd.concat(
            [returns[col], returns[benchmark]],
            axis=1
        ).dropna()

        if len(aligned) < 2:
            correlation_vs_bench[col] = np.nan
            covariance_vs_bench[col] = np.nan
        else:
            correlation_vs_bench[col] = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
            covariance_vs_bench[col] = aligned.iloc[:, 0].cov(aligned.iloc[:, 1])

    # ------------------------------------------
    # BUILD FINAL METRICS DF
    # ------------------------------------------

    metrics = pd.DataFrame({
        "Current Price": prices.iloc[-1],
        "Perf 1Y": perf_1y,
        "Perf 3Y": perf_3y,
        "Perf 5Y": perf_5y,
        "CAGR 3Y": cagr_3y,
        "CAGR 5Y": cagr_5y,
        "Avg Daily Return": avg_daily_return,
        "Annual Return": annual_return,
        "Skewness": skewness,
        "Kurtosis": kurtosis,
        "Correlation vs Benchmark": correlation_vs_bench,
        "Covariance vs Benchmark": covariance_vs_bench
    })

    return metrics, returns
