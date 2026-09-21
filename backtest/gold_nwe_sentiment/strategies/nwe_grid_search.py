"""Grid search fine sui parametri "puri" della banda NWE (senza sentiment/conferma/trend):
trova quale bandwidth/multiplier fa performare meglio la sola banda come strategia di
mean-reversion, su una griglia fitta (passo 0.1) invece della griglia rada usata altrove
(config.BANDWIDTH_RANGE/MULTIPLIER_RANGE, es. [6,8,10]).

Usa endpoint_line_errors_fast + bands_from_line_errors (vettorizzate via convoluzione)
invece della endpoint_envelope "di riferimento": la parte costosa (line/errors) si calcola
una sola volta per ogni bandwidth, poi ogni multiplier è quasi gratis — 200×200 combinazioni
sarebbero altrimenti troppo lente con il loop Python della versione di riferimento.

Stop/target ATR restano fissi (config.ATR_STOP_MULT/ATR_TARGET_MULT): con 40.000 combinazioni
di bandwidth×multiplier aggiungere anche quelli esploderebbe i tempi; quello si fa dopo, con
optimization.optimizer.compare_variants(), sulla manciata di bandwidth/multiplier migliori
trovati qui.
"""

import numpy as np
import pandas as pd

import config
from backtest.engine import backtest
from indicators.atr import atr
from indicators.nadaraya_watson import bands_from_line_errors, endpoint_line_errors_fast
from utils.metrics import max_drawdown, sharpe_ratio, total_return


def run_grid_search(
    data: pd.DataFrame,
    capital: float,
    risk_pct: float,
    periods_per_year: float = 252,
    bandwidth_range=None,
    multiplier_range=None,
    stop_mult: float = None,
    target_mult: float = None,
    lookback: int = None,
    min_trades: int = None,
) -> pd.DataFrame:
    """Ritorna un DataFrame con una riga per ogni (bandwidth, multiplier) valida, ordinato
    per Sharpe decrescente."""
    bandwidth_range = bandwidth_range if bandwidth_range is not None else config.FINE_BANDWIDTH_RANGE
    multiplier_range = multiplier_range if multiplier_range is not None else config.FINE_MULTIPLIER_RANGE
    stop_mult = stop_mult if stop_mult is not None else config.ATR_STOP_MULT
    target_mult = target_mult if target_mult is not None else config.ATR_TARGET_MULT
    lookback = lookback if lookback is not None else config.NWE_LOOKBACK
    min_trades = min_trades if min_trades is not None else config.MIN_TRADES

    close = data["Close"].to_numpy(dtype=float)
    atr_values = atr(data["High"], data["Low"], data["Close"], config.ATR_PERIOD).to_numpy()
    base = data[["High", "Low", "Close"]].copy()
    base["atr"] = atr_values

    results = []
    for bandwidth in bandwidth_range:
        line, errors = endpoint_line_errors_fast(close, bandwidth, lookback)

        for multiplier in multiplier_range:
            upper, lower = bands_from_line_errors(line, errors, multiplier, lookback)

            frame = base.copy()
            frame["signal"] = 0
            long_entry = close <= lower
            short_entry = close >= upper
            frame.loc[long_entry, "signal"] = 1
            frame.loc[short_entry, "signal"] = -1

            bt, trades, _ = backtest(frame, capital, risk_pct, stop_mult, target_mult)
            if len(trades) < min_trades:
                continue

            eq = bt["equity"].to_numpy()
            results.append({
                "bandwidth": round(float(bandwidth), 2),
                "multiplier": round(float(multiplier), 2),
                "trades": len(trades),
                "win_rate": trades["win"].mean(),
                "return": total_return(eq),
                "sharpe": sharpe_ratio(eq, periods_per_year),
                "max_drawdown": max_drawdown(eq),
            })

    df = pd.DataFrame(results)
    if df.empty:
        return df
    df.sort_values("sharpe", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df
