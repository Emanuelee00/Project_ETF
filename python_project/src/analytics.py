"""Advanced portfolio analytics (production-grade robust version)."""

import numpy as np
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

RISK_FREE_RATE = 0.02
TRADING_DAYS = 252


# ---------------------------------------------------
# MULTI-SOURCE DATA FETCHER
# ---------------------------------------------------

def fetch_prices(tickers: list[str], period: str = "5y") -> pd.DataFrame:
    """Download price data with fallback sources and validation."""
    
    prices = _fetch_yahoo(tickers, period)
    
    if prices.empty:
        return _fetch_stooq(tickers, period)
    
    missing = [t for t in tickers if t not in prices.columns or prices[t].isna().all()]
    
    if missing:
        stooq_data = _fetch_stooq(missing, period)
        for t in missing:
            if t in stooq_data.columns:
                prices[t] = stooq_data[t]
    
    prices = prices.dropna(axis=1, how="all")
    
    return prices


def _fetch_yahoo(tickers: list[str], period: str = "5y") -> pd.DataFrame:
    """Primary source: Yahoo Finance."""
    try:
        data = yf.download(
            tickers,
            period=period,
            progress=False,
            threads=True,
            auto_adjust=False
        )
        
        if data.empty:
            return pd.DataFrame()
        
        if isinstance(data.columns, pd.MultiIndex):
            if "Adj Close" in data.columns.levels[0]:
                prices = data["Adj Close"]
            elif "Close" in data.columns.levels[0]:
                prices = data["Close"]
            else:
                return pd.DataFrame()
        else:
            if "Adj Close" in data.columns:
                prices = data["Adj Close"].to_frame(name=tickers[0])
            elif "Close" in data.columns:
                prices = data["Close"].to_frame(name=tickers[0])
            else:
                return pd.DataFrame()
        
        return prices.dropna(axis=1, how="all")
    except Exception as e:
        print(f"Yahoo fetch error: {e}")
        return pd.DataFrame()


def _fetch_stooq(tickers: list[str], period: str = "5y") -> pd.DataFrame:
    """Fallback: Stooq.com (free, no API key)."""
    period_map = {"1y": 365, "2y": 730, "3y": 1095, "5y": 1825, "10y": 3650}
    days = period_map.get(period, 1825)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    result = {}
    
    for ticker in tickers:
        try:
            if ".L" in ticker:
                stooq_ticker = ticker.replace(".L", "") + ".L"
            elif ".AS" in ticker:
                stooq_ticker = ticker.replace(".AS", "") + ".AS"
            else:
                stooq_ticker = ticker
            
            url = f"https://stooq.com/q/d/l/?s={stooq_ticker}&d1={start_date.strftime('%Y%m%d')}&d2={end_date.strftime('%Y%m%d')}"
            df = pd.read_csv(url, index_col="Date", parse_dates=True)
            
            if not df.empty and "Close" in df.columns:
                result[ticker] = df["Close"].sort_index()
        except:
            continue
    
    if result:
        return pd.DataFrame(result)
    return pd.DataFrame()


# ---------------------------------------------------
# DATA QUALITY VALIDATION
# ---------------------------------------------------

def validate_data_quality(prices: pd.DataFrame) -> dict:
    """Comprehensive data quality analysis."""
    report = {
        "total_assets": len(prices.columns),
        "issues": [],
        "warnings": [],
        "valid_assets": [],
        "completeness": {}
    }
    
    if prices.empty:
        report["issues"].append("No data retrieved")
        return report
    
    for col in prices.columns:
        series = prices[col].dropna()
        
        completeness = len(series) / len(prices) * 100
        report["completeness"][col] = completeness
        
        if completeness < 50:
            report["issues"].append(f"{col}: Only {completeness:.1f}% data completeness")
            continue
        
        if len(series) < 50:
            report["warnings"].append(f"{col}: Insufficient data ({len(series)} points)")
            continue
        
        returns = series.pct_change().dropna()
        
        if len(returns) > 0:
            max_return = returns.abs().max()
            if max_return > 0.5:
                report["issues"].append(f"{col}: Extreme daily return {max_return:.1%}")
                continue
            
            if (series <= 0).any():
                report["warnings"].append(f"{col}: Non-positive prices detected")
                continue
        
        report["valid_assets"].append(col)
    
    report["valid_count"] = len(report["valid_assets"])
    return report


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