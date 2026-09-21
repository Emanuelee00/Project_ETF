"""Recupero notizie sull'oro da Yahoo Finance (stesso meccanismo usato nel progetto principale)."""

from datetime import datetime, timezone

import yfinance as yf

from state import Article


def fetch_gold_news(ticker: str, limit: int = 20) -> list[Article]:
    """Scarica le notizie recenti disponibili per un ticker legato all'oro."""
    raw_news = yf.Ticker(ticker).news or []
    articles: list[Article] = []

    for item in raw_news[:limit]:
        if "content" in item and isinstance(item["content"], dict):
            c = item["content"]
            title = c.get("title", "")
            publisher = (c.get("provider") or {}).get("displayName", "")
            link = (c.get("canonicalUrl") or c.get("clickThroughUrl") or {}).get("url", "")
            pub_date = c.get("pubDate") or c.get("displayTime") or ""
            try:
                date_str = datetime.strptime(pub_date[:10], "%Y-%m-%d").strftime("%Y-%m-%d") if pub_date else "—"
            except Exception:
                date_str = "—"
        else:
            title = item.get("title", "")
            publisher = item.get("publisher", "")
            link = item.get("link", "")
            ts = item.get("providerPublishTime", 0)
            date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else "—"

        if not title:
            continue

        articles.append({"title": title, "publisher": publisher, "link": link, "date": date_str})

    return articles
