"""Full debug analysis for a single ticker."""

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from analytics import fetch_prices
from risk_metrics import (
    compute_volatility,
    compute_sharpe,
    compute_beta,
    compute_max_drawdown
)

BENCHMARK = "IWDA.AS"
TICKER = "020Y.L"
TRADING_DAYS = 252


def compute_cagr(prices, years):
    period = years * TRADING_DAYS
    if len(prices) < period:
        return np.nan
    p = prices.tail(period)
    return (p.iloc[-1] / p.iloc[0]) ** (1 / years) - 1


def compute_performance(prices, years):
    period = years * TRADING_DAYS
    if len(prices) < period:
        return np.nan
    p = prices.tail(period)
    return p.iloc[-1] / p.iloc[0] - 1


def main():

    print("\n" + "="*80)
    print(f"FULL DEBUG FOR {TICKER}")
    print("="*80)

    tickers = [TICKER, BENCHMARK]

    # ---------------- DOWNLOAD ----------------
    print("\nDownloading prices...")
    prices = fetch_prices(tickers)

    print("\nPrice Info:")
    print(prices.info())

    print("\nPrice Head:")
    print(prices.head())

    print("\nPrice Tail:")
    print(prices.tail())

    print("\nMissing values:")
    print(prices.isna().sum())

    # ---------------- RETURNS ----------------
    returns = prices.pct_change().dropna()

    print("\nReturns Info:")
    print(returns.info())

    print("\nReturns describe:")
    print(returns.describe())

    print("\nReturn observations:")
    print(returns.count())

    # ---------------- PERFORMANCE ----------------
    print("\nPERFORMANCE METRICS")
    print("-"*40)

    perf_1y = compute_performance(prices[TICKER], 1)
    perf_3y = compute_performance(prices[TICKER], 3)
    perf_5y = compute_performance(prices[TICKER], 5)

    cagr_3y = compute_cagr(prices[TICKER], 3)
    cagr_5y = compute_cagr(prices[TICKER], 5)

    print(f"Performance 1Y: {perf_1y}")
    print(f"Performance 3Y: {perf_3y}")
    print(f"Performance 5Y: {perf_5y}")
    print(f"CAGR 3Y: {cagr_3y}")
    print(f"CAGR 5Y: {cagr_5y}")

    # ---------------- RISK ----------------
    print("\nRISK METRICS")
    print("-"*40)

    vol = compute_volatility(returns)
    sharpe = compute_sharpe(returns)
    beta = compute_beta(returns, BENCHMARK)
    max_dd = compute_max_drawdown(returns)

    print(f"Volatility: {vol[TICKER]}")
    print(f"Sharpe: {sharpe[TICKER]}")
    print(f"Beta: {beta[TICKER]}")
    print(f"Max Drawdown: {max_dd[TICKER]}")

    # ---------------- EXTRA DIAGNOSTICS ----------------
    print("\nCORRELATION & COVARIANCE")
    print("-"*40)

    corr = returns.corr()
    print("Correlation matrix:")
    print(corr)

    aligned = pd.concat([returns[TICKER], returns[BENCHMARK]], axis=1).dropna()
    cov = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])[0, 1]
    var_bench = np.var(aligned.iloc[:, 1])

    print(f"\nCovariance: {cov}")
    print(f"Benchmark variance: {var_bench}")

    # ---------------- DRAWDOWN SERIES ----------------
    print("\nDRAWDOWN SERIES")
    print("-"*40)

    cumulative = (1 + returns[TICKER]).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max

    print("Worst 10 drawdowns:")
    print(drawdown.sort_values().head(10))

    print("\n" + "="*80)
    print("DEBUG COMPLETED")
    print("="*80)


    # ================= DASHBOARD 2x2 =================

    print("\nBuilding dashboard...")

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    # -------------------------------------------------
    # 1) PRICE SERIES
    # -------------------------------------------------
    axes[0, 0].plot(prices.index, prices[TICKER], label=TICKER)
    axes[0, 0].plot(prices.index, prices[BENCHMARK], label=BENCHMARK, alpha=0.7)
    axes[0, 0].set_title("Price Series")
    axes[0, 0].legend()
    axes[0, 0].grid(True)

    # -------------------------------------------------
    # 2) CUMULATIVE RETURNS
    # -------------------------------------------------
    cumulative_returns = (1 + returns).cumprod()

    axes[0, 1].plot(cumulative_returns.index, cumulative_returns[TICKER], label=TICKER)
    axes[0, 1].plot(cumulative_returns.index, cumulative_returns[BENCHMARK], label=BENCHMARK)
    axes[0, 1].set_title("Cumulative Returns (Growth of 1)")
    axes[0, 1].legend()
    axes[0, 1].grid(True)

    # -------------------------------------------------
    # 3) DRAWDOWN (UNDERWATER)
    # -------------------------------------------------
    axes[1, 0].plot(drawdown.index, drawdown)
    axes[1, 0].set_title("Drawdown")
    axes[1, 0].grid(True)

    # -------------------------------------------------
    # 4) ROLLING VOLATILITY (1Y)
    # -------------------------------------------------
    rolling_vol = returns[TICKER].rolling(252).std() * np.sqrt(252)

    axes[1, 1].plot(rolling_vol.index, rolling_vol)
    axes[1, 1].set_title("Rolling 1Y Volatility")
    axes[1, 1].grid(True)

    plt.suptitle(f"Full Diagnostic Dashboard - {TICKER}", fontsize=16)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
