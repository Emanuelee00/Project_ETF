"""Parametri globali: strategia Nadaraya-Watson Envelope (no-repaint) + filtro sentiment sull'oro."""

import numpy as np

TICKER = "GC=F"
INTERVAL = "15m"
PERIOD = "60d"  # yfinance limita le barre a 15 minuti a ~60 giorni di storico

INITIAL_CAPITAL = 100_000.0
RISK_PER_TRADE = 1.0  # % di equity rischiata per trade (distanza tra entry e stop)

# Nadaraya-Watson Envelope (endpoint / no-repaint) — stessi default della UI web
NWE_BANDWIDTH = 8
NWE_MULTIPLIER = 3
NWE_LOOKBACK = 500

# Stop-loss / take-profit basati su ATR
ATR_PERIOD = 14
ATR_STOP_MULT = 1.5
ATR_TARGET_MULT = 2.5

# Filtro sentiment: soglia di veto sullo score continuo (-100..100), più permissiva della
# soglia ±20 che gold_agent usa per decidere BUY/SELL/HOLD, così più giorni influenzano
# davvero il filtro invece di finire tutti in "HOLD" (vedi strategies/nwe_sentiment_strategy.py)
SENTIMENT_VETO = 15
SENTIMENT_VETO_RANGE = [10, 15, 20]

# Grid search
BANDWIDTH_RANGE = [6, 8, 10]
MULTIPLIER_RANGE = [2, 3, 4]
ATR_STOP_RANGE = [1.0, 1.5, 2.0]
ATR_TARGET_RANGE = [2.0, 2.5, 3.0]
MIN_TRADES = 10

# Filtri di entrata opzionali (vedi strategies/nwe_sentiment_strategy.py)
TREND_EMA_PERIOD = 200     # EMA lunga sui 15m, approssima il trend di un timeframe superiore
TREND_SLOPE_LOOKBACK = 5   # barre su cui misurare se la EMA sta salendo o scendendo

# Varianti confrontate da main.py: candela di conferma/rifiuto e filtro di trend,
# singolarmente e insieme, per vedere quale migliora davvero il win rate
VARIANTS = [
    {"name": "baseline", "use_confirmation": False, "use_trend_filter": False},
    {"name": "confirmation", "use_confirmation": True, "use_trend_filter": False},
    {"name": "trend_filter", "use_confirmation": False, "use_trend_filter": True},
    {"name": "confirm+trend", "use_confirmation": True, "use_trend_filter": True},
]

# Grid search fine sulla sola banda NWE (strategies/nwe_grid_search.py, run_nwe_grid_search.py):
# finestra 0.1-20.0 passo 0.1 per bandwidth e multiplier, 200x200 combinazioni. np.round evita
# i classici errori di arrotondamento in virgola mobile di np.arange con step piccoli.
FINE_BANDWIDTH_RANGE = np.round(np.arange(0.1, 20.0 + 1e-9, 0.1), 2)
FINE_MULTIPLIER_RANGE = np.round(np.arange(0.1, 20.0 + 1e-9, 0.1), 2)

# File di handoff: run_nwe_grid_search.py ci scrive il bandwidth/multiplier migliore trovato,
# main.py li legge (se presenti) al posto di BANDWIDTH_RANGE/MULTIPLIER_RANGE
BEST_NWE_PARAMS_PATH = "best_nwe_params.json"

# DB del sentiment giornaliero salvato da gold_agent (cartella sibling)
GOLD_SENTIMENT_DB = "../../gold_agent/gold_sentiment.db"
