"""Production-grade ISIN -> Ticker automatic mapping."""

import time
import random
import logging
import requests
import pandas as pd
import yfinance as yf
from tqdm import tqdm


INPUT_FILE = "himalaya.csv"
OUTPUT_FILE = "isin_ticker_mapping.csv"
LOG_FILE = "mapping.log"


# ------------------ Logging Setup ------------------

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logging.info("Starting mapping process.")


# ------------------ Yahoo Search ------------------

def search_ticker(isin: str, retries: int = 3) -> str | None:
    """Search ticker on Yahoo Finance with retry logic."""
    
    url = f"https://query1.finance.yahoo.com/v1/finance/search?q={isin}"

    for attempt in range(retries):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            data = response.json()
            return data["quotes"][0]["symbol"]
        except Exception:
            time.sleep(random.uniform(1, 2))

    return None


def validate_ticker(ticker: str) -> bool:
    """Validate ticker using yfinance."""
    try:
        data = yf.download(ticker, period="5d", progress=False)
        return not data.empty
    except Exception:
        return False


# ------------------ Main Mapping ------------------

def create_mapping():
    """Create or resume mapping process."""

    df = pd.read_csv(INPUT_FILE)
    isins = df["Code ISIN"].dropna().unique()

    if pd.io.common.file_exists(OUTPUT_FILE):
        existing = pd.read_csv(OUTPUT_FILE)
        processed = set(existing["ISIN"])
        mapping = existing.to_dict("records")
        print(f"Resuming from {len(processed)} already processed.")
    else:
        mapping = []
        processed = set()

    valid_count = 0
    invalid_count = 0

    start_time = time.time()

    for isin in tqdm(isins, desc="Mapping ISIN", unit="ISIN"):

        if isin in processed:
            continue

        ticker = search_ticker(isin)

        if ticker and validate_ticker(ticker):
            status = "VALID"
            valid_count += 1
        else:
            ticker = None
            status = "INVALID"
            invalid_count += 1

        tqdm.write(f"{isin} -> {ticker} [{status}]")
        logging.info(f"{isin} -> {ticker} [{status}]")

        mapping.append({"ISIN": isin, "Ticker": ticker})
        pd.DataFrame(mapping).to_csv(OUTPUT_FILE, index=False)

        time.sleep(random.uniform(0.8, 1.4))

    elapsed = round(time.time() - start_time, 2)

    print("\n========== MAPPING REPORT ==========")
    print(f"Total ISIN: {len(isins)}")
    print(f"Valid tickers: {valid_count}")
    print(f"Invalid tickers: {invalid_count}")
    print(f"Success rate: {round(valid_count / len(isins) * 100, 2)}%")
    print(f"Elapsed time: {elapsed} seconds")
    print("====================================")

    logging.info("Mapping completed.")


if __name__ == "__main__":
    create_mapping()
