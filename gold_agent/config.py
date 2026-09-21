"""Configurazione del gold agent: modello LLM locale, ticker, soglie del ciclo."""

import os

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

# Ticker Yahoo Finance da provare, in ordine, per rappresentare l'oro
GOLD_TICKERS = ["GC=F", "GLD", "XAUUSD=X"]

# Numero minimo di articoli utili prima di fermare il ciclo di raccolta notizie
MIN_ARTICLES = 5
# Numero massimo di tentativi di raccolta (uno per ticker in GOLD_TICKERS)
MAX_FETCH_ATTEMPTS = len(GOLD_TICKERS)
# Numero massimo di articoli analizzati dall'LLM per contenere i tempi
MAX_ARTICLES_TO_ANALYZE = 15

# Soglie per il segnale complessivo (media dei punteggi di sentiment, -100..100)
BUY_THRESHOLD = 20
SELL_THRESHOLD = -20

# --- Backfill storico via GDELT (backfill_gold_history.py) ---
GDELT_QUERY = '("gold price" OR "gold prices" OR "gold bullion" OR "price of gold") sourcelang:english'
# Ampiezza di ogni finestra temporale interrogata (GDELT limita i record per richiesta)
GDELT_CHUNK_DAYS = 7
# Pausa tra una richiesta e l'altra: GDELT risponde 429 sotto i 5 secondi tra due chiamate
GDELT_REQUEST_DELAY_SECONDS = 6
# Articoli analizzati dall'LLM per ciascuna finestra, per contenere i tempi su un anno intero
MAX_ARTICLES_PER_BACKFILL_CHUNK = 8
BACKFILL_DEFAULT_DAYS = 365
