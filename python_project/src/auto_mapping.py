"""Automatic ISIN -> Ticker mapping using Yahoo search."""

import os
import requests
import pandas as pd


def search_ticker_from_isin(isin: str) -> str | None:
    """Search ticker on Yahoo Finance using ISIN."""
    url = f"https://query1.finance.yahoo.com/v1/finance/search?q={isin}"
    response = requests.get(url)
    data = response.json()

    try:
        return data["quotes"][0]["symbol"]
    except (KeyError, IndexError):
        return None


def create_mapping_if_missing():
    """Create ISIN mapping automatically if missing."""
    mapping_path = "data/isin_ticker_mapping.csv"

    if os.path.exists(mapping_path):
        print("Mapping already exists.")
        return pd.read_csv(mapping_path)

    print("Creating ISIN -> Ticker mapping via Yahoo...")

    df = pd.read_csv("data/himalaya.csv")
    isins = df.iloc[:, 1].dropna().unique()

    mapping = []

    for isin in isins:
        ticker = search_ticker_from_isin(isin)
        print(f"{isin} -> {ticker}")
        mapping.append({"ISIN": isin, "Ticker": ticker})

    mapping_df = pd.DataFrame(mapping)
    mapping_df.to_csv(mapping_path, index=False)

    return mapping_df
