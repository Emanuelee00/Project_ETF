import pandas as pd
import numpy as np


def compute_weekly_seasonality_full(returns: pd.DataFrame):
    """
    Computes full 52-week seasonality statistics.

    Returns:
        dict:
            asset_name -> DataFrame (52 rows)
    """

    returns = returns.copy()
    returns.index = pd.to_datetime(returns.index)

    seasonality_dict = {}

    for asset in returns.columns:

        series = returns[asset].dropna()

        if len(series) < 252:
            continue

        # Convert daily returns to weekly compounded returns
        weekly = (1 + series).resample("W-FRI").prod() - 1

        df = weekly.to_frame(name="return")
        df["year"] = df.index.year
        df["week"] = df.index.isocalendar().week.astype(int)

        pivot = df.pivot(index="week", columns="year", values="return")

        # Keep only weeks 1–52
        pivot = pivot.loc[pivot.index <= 52]

        if pivot.shape[1] < 2:
            continue

        stats = pd.DataFrame(index=pivot.index)

        stats["Average_Return"] = pivot.mean(axis=1)
        stats["Std_Dev"] = pivot.std(axis=1)
        stats["Positive_Ratio"] = (pivot > 0).mean(axis=1)
        stats["T_Stat"] = stats["Average_Return"] / (
            stats["Std_Dev"] / np.sqrt(pivot.shape[1])
        )

        seasonality_dict[asset] = {
            "matrix": pivot,
            "stats": stats
        }

    return seasonality_dict

MIN_YEARS_REQUIRED = 2


def compute_multi_horizon_seasonality(returns: pd.DataFrame):
    """
    Computes weekly seasonality stability score for each asset.

    Returns:
        DataFrame with:
        - Weekly_Seasonality (correlation stability)
        - Avg_Weekly_Return
        - Weekly_Volatility
        - Rank
    """

    returns = returns.copy()
    returns.index = pd.to_datetime(returns.index)

    results = {}

    for asset in returns.columns:

        series = returns[asset].dropna()

        if len(series) < 252:
            results[asset] = {
                "Weekly_Seasonality": np.nan,
                "Avg_Weekly_Return": np.nan,
                "Weekly_Volatility": np.nan,
            }
            continue

        # Convert daily returns to weekly compounded returns
        weekly = (1 + series).resample("W-FRI").prod() - 1

        df = weekly.to_frame(name="return")
        df["year"] = df.index.year
        df["week"] = df.index.isocalendar().week.astype(int)

        pivot = df.pivot(index="week", columns="year", values="return")

        if pivot.shape[1] < MIN_YEARS_REQUIRED:
            results[asset] = {
                "Weekly_Seasonality": np.nan,
                "Avg_Weekly_Return": np.nan,
                "Weekly_Volatility": np.nan,
            }
            continue

        # Stability score (correlation between years)
        corr = pivot.corr()
        mask = np.triu(np.ones(corr.shape), k=1).astype(bool)
        stability_score = corr.where(mask).stack().mean()

        # Average weekly return across all weeks
        avg_weekly_return = weekly.mean()

        # Weekly volatility
        weekly_volatility = weekly.std()

        results[asset] = {
            "Weekly_Seasonality": stability_score,
            "Avg_Weekly_Return": avg_weekly_return,
            "Weekly_Volatility": weekly_volatility,
        }

    result_df = pd.DataFrame(results).T

    # Ranking (higher stability first)
    result_df["Rank"] = result_df["Weekly_Seasonality"].rank(
        ascending=False,
        method="min"
    )

    return result_df


def compute_weekly_seasonality_multi(returns: pd.DataFrame):

    returns = returns.copy()
    returns.index = pd.to_datetime(returns.index)

    seasonality_dict = {}

    for asset in returns.columns:

        series = returns[asset].dropna()

        if len(series) < 252:
            continue

        weekly = (1 + series).resample("W-FRI").prod() - 1

        df = weekly.to_frame(name="return")
        df["year"] = df.index.year
        df["week"] = df.index.isocalendar().week.astype(int)

        pivot = df.pivot(index="week", columns="year", values="return")
        pivot = pivot.loc[pivot.index <= 52]

        pivot = pivot.sort_index(axis=1)

        seasonality_dict[asset] = pivot

    return seasonality_dict