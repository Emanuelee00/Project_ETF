"""Backfill storico: scarica notizie passate sull'oro da GDELT e le analizza con l'LLM locale.

GDELT (https://www.gdeltproject.org) è un archivio di notizie globale, gratuito e
senza API key, interrogabile per parola chiave e intervallo di date fino a diversi
anni indietro. yfinance invece non ha uno storico notizie (vedi news_fetcher.py),
quindi questo script serve solo a riempire il passato: il ciclo quotidiano in
main.py resta su yfinance + Ollama per le notizie del giorno corrente.

Uso:
    venv/bin/python backfill_gold_history.py              # ultimo anno (default)
    venv/bin/python backfill_gold_history.py --days 90     # ultimi 90 giorni
"""

import argparse
import time
from datetime import datetime, timedelta, timezone

import requests

import config
import storage
from llm_sentiment import analyze_sentiment

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def _fetch_gdelt_chunk(start: datetime, end: datetime, retries: int = 3) -> list[dict]:
    params = {
        "query": config.GDELT_QUERY,
        "mode": "artlist",
        "format": "json",
        "maxrecords": 250,
        "sort": "datedesc",
        "startdatetime": start.strftime("%Y%m%d%H%M%S"),
        "enddatetime": end.strftime("%Y%m%d%H%M%S"),
    }

    for attempt in range(retries):
        resp = requests.get(GDELT_URL, params=params, timeout=30, headers={"User-Agent": "gold-agent/0.1"})
        if resp.status_code == 429 and attempt < retries - 1:
            # GDELT è un servizio gratuito condiviso: sotto carico risponde 429 anche
            # rispettando GDELT_REQUEST_DELAY_SECONDS, quindi si aspetta di più e si ritenta.
            wait = config.GDELT_REQUEST_DELAY_SECONDS * (2 ** (attempt + 1))
            print(f"  GDELT 429, ritento tra {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json().get("articles", [])

    return []


def _to_article(raw: dict) -> dict:
    seendate = raw.get("seendate", "")
    try:
        date_str = datetime.strptime(seendate[:8], "%Y%m%d").strftime("%Y-%m-%d")
    except Exception:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return {
        "title": raw.get("title", ""),
        "publisher": raw.get("domain", ""),
        "link": raw.get("url", ""),
        "date": date_str,
    }


def backfill(days: int) -> None:
    known_links = storage.existing_links()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    cursor = start
    total_new = 0

    while cursor < end:
        chunk_end = min(cursor + timedelta(days=config.GDELT_CHUNK_DAYS), end)
        print(f"GDELT {cursor.date()} -> {chunk_end.date()}")

        try:
            raw_articles = _fetch_gdelt_chunk(cursor, chunk_end)
        except Exception as exc:
            print(f"  errore GDELT: {exc}")
            raw_articles = []

        candidates = [_to_article(a) for a in raw_articles if a.get("title") and a.get("url")]
        candidates = [a for a in candidates if a["link"] not in known_links]

        # GDELT restituisce spesso lo stesso articolo pubblicato su più siti "specchio"
        # (stesso titolo, link diversi): tenerne uno solo evita di sprecare chiamate LLM.
        seen_titles = set()
        deduped = []
        for article in candidates:
            if article["title"] in seen_titles:
                continue
            seen_titles.add(article["title"])
            deduped.append(article)
        candidates = deduped[: config.MAX_ARTICLES_PER_BACKFILL_CHUNK]

        analyzed = []
        for article in candidates:
            result = analyze_sentiment(article["title"], article["publisher"])
            analyzed.append({**article, **result})
            known_links.add(article["link"])

        if analyzed:
            new_count = storage.save_backfill(analyzed)
            total_new += new_count
            print(f"  +{new_count} articoli nuovi analizzati")

        cursor = chunk_end
        time.sleep(config.GDELT_REQUEST_DELAY_SECONDS)

    print(f"Backfill completato: {total_new} articoli nuovi salvati in totale.")


def main():
    parser = argparse.ArgumentParser(description="Backfill storico notizie sull'oro da GDELT")
    parser.add_argument("--days", type=int, default=config.BACKFILL_DEFAULT_DAYS)
    args = parser.parse_args()
    backfill(args.days)


if __name__ == "__main__":
    main()
