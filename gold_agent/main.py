"""Entry point: esegue il ciclo agentico di sentiment analysis con un LLM locale.

Pensato per essere lanciato una volta al giorno (es. da cron): ogni run salva gli
articoli nuovi in gold_sentiment.db, così lo storico giornaliero si accumula nel tempo.

Il mercato è selezionabile con --market, ma per ora il ciclo (ticker, query GDELT, prompt
LLM) è scritto solo per l'oro — passare un mercato diverso si ferma con un errore chiaro
invece di girare a vuoto, finché non verrà aggiunto davvero.
"""

import argparse
import sys

from graph import build_graph
from storage import daily_history

SUPPORTED_MARKETS = {"oro", "gold"}


def main():
    parser = argparse.ArgumentParser(description="Ciclo agentico di sentiment analysis su notizie di mercato")
    parser.add_argument("--market", default="oro", help="Mercato da analizzare (per ora solo 'oro')")
    args = parser.parse_args()

    if args.market.strip().lower() not in SUPPORTED_MARKETS:
        print(f"Mercato '{args.market}' non ancora supportato — per ora solo 'oro'.")
        sys.exit(1)

    app = build_graph()
    result = app.invoke({"articles": [], "analyzed": [], "tickers_tried": [], "attempts": 0})

    print(result["summary"])
    print(f"Articoli nuovi salvati nello storico: {result['new_articles_saved']}")
    print()
    for article in result["analyzed"]:
        print(f"[{article['sentiment']:>8} {article['score']:+4}] {article['title']}")
        print(f"    {article['reasoning']}")
        print(f"    {article['publisher']} - {article['date']} - {article['link']}")
        print()

    history = daily_history(14)
    if history:
        print("--- Storico ultimi giorni (dal più recente) ---")
        for day in history:
            print(f"{day['date']}  {day['signal']:>4}  score={day['overall_score']:+.1f}  articoli={day['articles_count']}")


if __name__ == "__main__":
    main()
