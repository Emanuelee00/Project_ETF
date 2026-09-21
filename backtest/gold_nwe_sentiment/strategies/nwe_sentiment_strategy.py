"""Mean-reversion sulla banda Nadaraya-Watson (no-repaint), filtrata dal sentiment giornaliero,
con due filtri di entrata opzionali (attivabili singolarmente o insieme, vedi config.VARIANTS):

- `use_confirmation`: invece di entrare al semplice tocco della banda (`Close` oltre la banda),
  richiede una candela di RIFIUTO — il prezzo perfora la banda con Low/High ma il Close torna
  dentro — per scartare gli ingressi che vengono travolti da un trend che continua a sfondare.
- `use_trend_filter`: non fa mean-reversion contro un trend di più lungo periodo (EMA a
  TREND_EMA_PERIOD barre, in discesa/salita da TREND_SLOPE_LOOKBACK barre) — es. non compra
  sulla banda inferiore se il trend di fondo sta chiaramente scendendo.

Il filtro sentiment usa lo SCORE continuo (-100..100) salvato da gold_agent, non solo
l'etichetta BUY/SELL/HOLD: quest'ultima scatta solo oltre ±20 (soglia di gold_agent per il
segnale del giorno), quindi molti giorni con uno score comunque marcato finirebbero tutti in
"HOLD" e il filtro non farebbe nulla. Con `sentiment_veto` configurabile (default più
permissivo di ±20) più giorni influenzano davvero il filtro. Resta comunque un filtro
DIREZIONALE giornaliero (cambia una volta al giorno), non una conferma bar-per-bar: la banda
invece si muove a ogni barra da 15 minuti — un disallineamento di granularità voluto.

Diviso in passi separati (build_bands / attach_sentiment / apply_entry_filters) così la grid
search può ricalcolare solo i filtri, più economici, senza rifare la banda NWE ad ogni prova.
"""

import pandas as pd

import config
from indicators.atr import atr
from indicators.nadaraya_watson import endpoint_envelope


def build_bands(data: pd.DataFrame, bandwidth: int = None, multiplier: float = None, lookback: int = None) -> pd.DataFrame:
    """Banda NWE, ATR, tocchi/rifiuti di banda e trend di fondo — indipendente dal sentiment."""
    bandwidth = bandwidth if bandwidth is not None else config.NWE_BANDWIDTH
    multiplier = multiplier if multiplier is not None else config.NWE_MULTIPLIER
    lookback = lookback if lookback is not None else config.NWE_LOOKBACK

    result = data.copy()
    close = result["Close"].to_numpy(dtype=float)
    line, upper, lower = endpoint_envelope(close, bandwidth, multiplier, lookback)
    result["nwe_line"] = line
    result["nwe_upper"] = upper
    result["nwe_lower"] = lower
    result["atr"] = atr(result["High"], result["Low"], result["Close"], config.ATR_PERIOD).values

    result["touch_lower"] = result["Close"] <= result["nwe_lower"]
    result["touch_upper"] = result["Close"] >= result["nwe_upper"]
    # Candela di rifiuto: perfora la banda ma chiude di nuovo dentro
    result["confirm_lower"] = (result["Low"] <= result["nwe_lower"]) & (result["Close"] > result["nwe_lower"])
    result["confirm_upper"] = (result["High"] >= result["nwe_upper"]) & (result["Close"] < result["nwe_upper"])

    trend_ema = result["Close"].ewm(span=config.TREND_EMA_PERIOD, adjust=False).mean()
    result["trend_ema"] = trend_ema
    result["trend_up"] = trend_ema.diff(config.TREND_SLOPE_LOOKBACK) > 0
    result["trend_down"] = trend_ema.diff(config.TREND_SLOPE_LOOKBACK) < 0
    return result


def attach_sentiment(data: pd.DataFrame, sentiment: dict) -> pd.DataFrame:
    """Score e segnale giornaliero di gold_agent allineati a ogni barra del giorno."""
    result = data.copy()
    days = pd.Series(result.index.strftime("%Y-%m-%d"), index=result.index)
    result["sentiment_score"] = days.map(lambda d: sentiment.get(d, {}).get("score", 0.0)).astype(float).values
    result["sentiment_label"] = days.map(lambda d: sentiment.get(d, {}).get("signal", "HOLD")).values
    return result


def apply_entry_filters(
    data: pd.DataFrame,
    sentiment_veto: float = None,
    use_confirmation: bool = False,
    use_trend_filter: bool = False,
) -> pd.DataFrame:
    """Applica soglia sentiment + (opzionale) candela di conferma + (opzionale) filtro trend."""
    sentiment_veto = sentiment_veto if sentiment_veto is not None else config.SENTIMENT_VETO

    result = data.copy()
    raw_long = result["confirm_lower"] if use_confirmation else result["touch_lower"]
    raw_short = result["confirm_upper"] if use_confirmation else result["touch_upper"]

    long_entry = raw_long & (result["sentiment_score"] > -sentiment_veto)
    short_entry = raw_short & (result["sentiment_score"] < sentiment_veto)

    if use_trend_filter:
        long_entry &= ~result["trend_down"].fillna(False)
        short_entry &= ~result["trend_up"].fillna(False)

    signal = pd.Series(0, index=result.index)
    signal[long_entry] = 1
    signal[short_entry] = -1
    result["signal"] = signal
    return result


def build_signals(
    data: pd.DataFrame,
    sentiment: dict,
    bandwidth: int = None,
    multiplier: float = None,
    lookback: int = None,
    sentiment_veto: float = None,
    use_confirmation: bool = False,
    use_trend_filter: bool = False,
) -> pd.DataFrame:
    """Pipeline completa: banda NWE + sentiment + filtri → colonna 'signal'."""
    bands = build_bands(data, bandwidth, multiplier, lookback)
    with_sentiment = attach_sentiment(bands, sentiment)
    return apply_entry_filters(with_sentiment, sentiment_veto, use_confirmation, use_trend_filter)
