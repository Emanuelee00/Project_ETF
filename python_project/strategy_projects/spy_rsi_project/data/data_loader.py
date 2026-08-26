"""Scarica prezzi da Yahoo Finance."""

import yfinance as yf


def load_data(symbol: str, interval: str = "1d"):
    """Ritorna DataFrame con colonna 'Close'."""
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="10y", interval=interval)
    df = df[["Close"]].copy()
    df.dropna(inplace=True)
    return df
