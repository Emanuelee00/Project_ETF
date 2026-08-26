"""Country detection from ISIN prefix or ticker exchange suffix."""

ISIN_COUNTRY_MAP = {
    "US": "USA", "GB": "UK", "IE": "Ireland", "LU": "Luxembourg",
    "FR": "France", "DE": "Germany", "NL": "Netherlands", "CH": "Switzerland",
    "IT": "Italy", "SE": "Sweden", "BE": "Belgium", "ES": "Spain",
    "AT": "Austria", "DK": "Denmark", "NO": "Norway", "FI": "Finland",
    "CA": "Canada", "AU": "Australia", "JP": "Japan", "SG": "Singapore",
}

TICKER_SUFFIX_COUNTRY_MAP = {
    ".L": "UK", ".IL": "UK", ".PA": "France",
    ".DE": "Germany", ".F": "Germany", ".MU": "Germany",
    ".MI": "Italy", ".SW": "Switzerland",
    ".AS": "Netherlands", ".SI": "Singapore",
}


def detect_country(ticker: str | None = None, isin: str | None = None) -> str:
    if isin:
        prefix = isin[:2].upper()
        if prefix in ISIN_COUNTRY_MAP:
            return ISIN_COUNTRY_MAP[prefix]

    if ticker:
        for suffix, country in TICKER_SUFFIX_COUNTRY_MAP.items():
            if ticker.endswith(suffix):
                return country

    return "Other"
