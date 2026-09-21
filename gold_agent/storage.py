"""Persistenza SQLite dello storico giornaliero di notizie e sentiment sull'oro.

yfinance non offre un archivio storico di notizie (`.news` restituisce solo lo
snapshot attuale), quindi lo storico si costruisce accumulando un'esecuzione
al giorno (es. via cron) invece di poter scaricare notizie passate.
"""

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import config

DB_PATH = Path(__file__).resolve().parent / "gold_sentiment.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    link TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    publisher TEXT,
    article_date TEXT,
    sentiment TEXT NOT NULL,
    score INTEGER NOT NULL,
    reasoning TEXT,
    fetched_on TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_summary (
    fetched_on TEXT PRIMARY KEY,
    articles_count INTEGER NOT NULL,
    overall_score REAL NOT NULL,
    signal TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def save_run(analyzed: list[dict], overall_score: float, signal: str) -> int:
    """Salva gli articoli analizzati oggi e il riepilogo giornaliero.

    Ritorna quanti articoli erano nuovi (non ancora visti in run precedenti).
    """
    today = date.today().isoformat()
    new_count = 0

    with closing(_connect()) as conn:
        for article in analyzed:
            link = article.get("link") or article["title"]
            cur = conn.execute(
                "INSERT OR IGNORE INTO articles "
                "(link, title, publisher, article_date, sentiment, score, reasoning, fetched_on) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    link,
                    article["title"],
                    article.get("publisher", ""),
                    article.get("date", ""),
                    article["sentiment"],
                    article["score"],
                    article.get("reasoning", ""),
                    today,
                ),
            )
            new_count += cur.rowcount

        conn.execute(
            "INSERT OR REPLACE INTO daily_summary (fetched_on, articles_count, overall_score, signal) "
            "VALUES (?, ?, ?, ?)",
            (today, len(analyzed), overall_score, signal),
        )
        conn.commit()

    return new_count


def existing_links() -> set[str]:
    """Link già presenti in archivio, per evitare di rianalizzare gli stessi articoli col backfill."""
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT link FROM articles").fetchall()
    return {r[0] for r in rows}


def _signal_for(score: float) -> str:
    if score >= config.BUY_THRESHOLD:
        return "BUY"
    if score <= config.SELL_THRESHOLD:
        return "SELL"
    return "HOLD"


def save_backfill(analyzed: list[dict]) -> int:
    """Salva articoli storici sotto la loro data reale di pubblicazione (non "oggi") e
    ricalcola il riepilogo giornaliero per i giorni toccati.

    Usata da backfill_gold_history.py, a differenza di save_run() che invece registra
    sempre lo snapshot odierno della run quotidiana.
    """
    new_count = 0
    touched_dates: set[str] = set()

    with closing(_connect()) as conn:
        for article in analyzed:
            fetched_on = article.get("date") or date.today().isoformat()
            link = article.get("link") or article["title"]
            cur = conn.execute(
                "INSERT OR IGNORE INTO articles "
                "(link, title, publisher, article_date, sentiment, score, reasoning, fetched_on) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    link,
                    article["title"],
                    article.get("publisher", ""),
                    article.get("date", ""),
                    article["sentiment"],
                    article["score"],
                    article.get("reasoning", ""),
                    fetched_on,
                ),
            )
            if cur.rowcount:
                new_count += 1
                touched_dates.add(fetched_on)

        for day in touched_dates:
            count, avg_score = conn.execute(
                "SELECT COUNT(*), AVG(score) FROM articles WHERE fetched_on = ?", (day,)
            ).fetchone()
            avg_score = avg_score or 0.0
            conn.execute(
                "INSERT OR REPLACE INTO daily_summary (fetched_on, articles_count, overall_score, signal) "
                "VALUES (?, ?, ?, ?)",
                (day, count, round(avg_score, 1), _signal_for(avg_score)),
            )

        conn.commit()

    return new_count


def daily_history(days: int = 30) -> list[dict]:
    """Ritorna il riepilogo giornaliero salvato finora, dal più recente."""
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT fetched_on, articles_count, overall_score, signal "
            "FROM daily_summary ORDER BY fetched_on DESC LIMIT ?",
            (days,),
        ).fetchall()

    return [{"date": r[0], "articles_count": r[1], "overall_score": r[2], "signal": r[3]} for r in rows]
