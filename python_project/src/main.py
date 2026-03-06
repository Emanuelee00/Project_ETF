"""Main portfolio execution script (stable professional version)."""

import pandas as pd
from pathlib import Path
from analytics import fetch_prices, compute_metrics
from optimization import optimize_portfolios
from excel_export import export_to_excel
from risk_metrics import (
    compute_volatility,
    compute_sharpe,
    compute_beta,
    compute_max_drawdown
)
from seasonality import compute_weekly_seasonality_multi

# ------------------ Paths ------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

OUTPUT_DIR.mkdir(exist_ok=True)

MAPPING_FILE = DATA_DIR / "isin_ticker_mapping.csv"
ORIGINAL_FILE = DATA_DIR / "himalaya.csv"
OUTPUT_FILE = OUTPUT_DIR / "portfolio_analysis.xlsx"

BENCHMARK = "IWDA.AS"


# ------------------ Country Detection ------------------

def detect_country(ticker: str) -> str:

    exchange_map = {
        ".L": "UK",
        ".IL": "UK",
        ".PA": "France",
        ".DE": "Germany",
        ".F": "Germany",
        ".MU": "Germany",
        ".MI": "Italy",
        ".SW": "Switzerland",
        ".AS": "Netherlands",
        ".SI": "Singapore"
    }

    for suffix, country in exchange_map.items():
        if ticker.endswith(suffix):
            return country

    return "Other"


# ------------------ Main ------------------

def main():

    print("\n" + "=" * 60)
    print("PORTFOLIO ANALYSIS PIPELINE STARTED")
    print("=" * 60 + "\n")

    # --------------------------------------------------
    # LOAD MAPPING
    # --------------------------------------------------

    print("Loading mapping file...")
    mapping_df = pd.read_csv(MAPPING_FILE)
    mapping_df.columns = mapping_df.columns.str.strip()

    if "Ticker" not in mapping_df.columns:
        raise ValueError("Column 'Ticker' not found in mapping file.")

    tickers = (
        mapping_df["Ticker"]
        .dropna()
        .loc[lambda x: x != ""]
        .unique()
        .tolist()
    )

    if not tickers:
        raise ValueError("No valid tickers found.")

    if BENCHMARK not in tickers:
        tickers.append(BENCHMARK)

    print(f"Tickers loaded: {len(tickers)}")

    # --------------------------------------------------
    # DOWNLOAD DATA
    # --------------------------------------------------

    print("\nDownloading market data...")
    prices = fetch_prices(tickers)

    print(f"Assets with data: {prices.shape[1]}")
    print(f"Date range: {prices.index.min().date()} → {prices.index.max().date()}")

    # --------------------------------------------------
    # PERFORMANCE METRICS
    # --------------------------------------------------

    print("\nComputing performance metrics...")
    metrics_perf, returns = compute_metrics(prices, BENCHMARK)

    # --------------------------------------------------
    # RISK METRICS
    # --------------------------------------------------

    print("Computing risk metrics...")

    risk_df = pd.DataFrame({
        "Volatility 1Y": compute_volatility(returns),
        "Sharpe Ratio": compute_sharpe(returns),
        "Beta vs Benchmark": compute_beta(returns, BENCHMARK),
        "Max Drawdown": compute_max_drawdown(returns)
    })

    # Join safely on index
    metrics = metrics_perf.join(risk_df)

    # Remove benchmark row
    if BENCHMARK in metrics.index:
        metrics = metrics.drop(index=BENCHMARK)

    # --------------------------------------------------
    # ADD COUNTRY
    # --------------------------------------------------

    metrics["Country"] = metrics.index.map(detect_country)

    # --------------------------------------------------
    # ADD ETF NAMES (SAFE LOOKUP)
    # --------------------------------------------------

    print("Merging ETF names...")

    original_df = pd.read_csv(ORIGINAL_FILE)

    if "Code ISIN" in original_df.columns:

        name_map = original_df[["Code ISIN", original_df.columns[0]]].dropna()
        name_map.columns = ["ISIN", "Name"]

        merged = mapping_df.merge(name_map, on="ISIN", how="left")

        name_lookup = (
            merged[["Ticker", "Name"]]
            .drop_duplicates("Ticker")
            .set_index("Ticker")["Name"]
        )

        metrics["Name"] = metrics.index.map(name_lookup)

    else:
        metrics["Name"] = None

    # --------------------------------------------------
    # ADD ISIN COLUMN
    # --------------------------------------------------

    isin_lookup = (
        mapping_df[["Ticker", "ISIN"]]
        .drop_duplicates("Ticker")
        .set_index("Ticker")["ISIN"]
    )

    metrics["ISIN"] = metrics.index.map(isin_lookup)

    # --------------------------------------------------
    # REORDER COLUMNS (NO INDEX BREAKING)
    # --------------------------------------------------

    metrics.insert(0, "Name", metrics.pop("Name"))
    metrics.insert(1, "ISIN", metrics.pop("ISIN"))
    metrics.insert(2, "Country", metrics.pop("Country"))

    # --------------------------------------------------
    # PORTFOLIO OPTIMIZATION
    # --------------------------------------------------

    print("\nRunning portfolio optimization...")
    correlation = returns.corr()
    max_sharpe_dict, min_vol_dict = optimize_portfolios(returns)

    max_sharpe = pd.Series(max_sharpe_dict)
    min_vol = pd.Series(min_vol_dict)

    # --------------------------------------------------
    # REPLACE TICKERS WITH ETF NAMES (NO STRUCTURE CHANGE)
    # --------------------------------------------------

    if "Name" in metrics.columns:

        name_lookup = metrics["Name"].to_dict()

        # Correlation matrix
        correlation.index = correlation.index.map(
            lambda x: name_lookup.get(x, x)
        )
        correlation.columns = correlation.columns.map(
            lambda x: name_lookup.get(x, x)
        )

        # Max Sharpe
        max_sharpe.index = max_sharpe.index.map(
            lambda x: name_lookup.get(x, x)
        )

        # Min Vol
        min_vol.index = min_vol.index.map(
            lambda x: name_lookup.get(x, x)
        )

    weekly_seasonality = compute_weekly_seasonality_multi(returns)

    # --------------------------------------------------
    # EXPORT
    # --------------------------------------------------

    print("\nExporting Excel report...")

    export_to_excel(
        metrics,
        correlation,
        max_sharpe,
        min_vol,
        weekly_seasonality,
        OUTPUT_FILE
    )

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETED SUCCESSFULLY")
    print(f"Output file: {OUTPUT_FILE}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
