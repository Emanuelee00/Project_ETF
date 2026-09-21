"""Simulazione con stop-loss/take-profit basati su ATR e posizione singola a rischio fisso.

A differenza del motore "flat" degli altri strategy_projects (solo long/flat, uscita sul
segnale opposto), qui l'entrata su un tocco di banda non ha un'uscita naturale nel segnale:
serve uno stop e un target espliciti per sapere quanto si rischia per trade.
"""

import pandas as pd

import config


def backtest(
    data: pd.DataFrame,
    capital: float = None,
    risk_pct: float = None,
    stop_mult: float = None,
    target_mult: float = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict | None]:
    capital = capital if capital is not None else config.INITIAL_CAPITAL
    risk_pct = risk_pct if risk_pct is not None else config.RISK_PER_TRADE
    stop_mult = stop_mult if stop_mult is not None else config.ATR_STOP_MULT
    target_mult = target_mult if target_mult is not None else config.ATR_TARGET_MULT

    equity = capital
    position = 0  # +1 long, -1 short, 0 flat
    qty = entry_price = stop_price = target_price = 0.0
    entry_time = None
    equity_curve = []
    trades = []

    highs = data["High"].to_numpy()
    lows = data["Low"].to_numpy()
    closes = data["Close"].to_numpy()
    atrs = data["atr"].to_numpy()
    signals = data["signal"].to_numpy()
    index = data.index

    for i in range(len(data)):
        price = closes[i]

        if position != 0:
            hit_stop = (position == 1 and lows[i] <= stop_price) or (position == -1 and highs[i] >= stop_price)
            hit_target = (position == 1 and highs[i] >= target_price) or (position == -1 and lows[i] <= target_price)
            exit_price = stop_price if hit_stop else (target_price if hit_target else None)

            if exit_price is not None:
                pnl = (exit_price - entry_price) * qty * position
                equity += pnl
                trades.append({
                    "direction": "long" if position == 1 else "short",
                    "entry_time": entry_time,
                    "entry_price": entry_price,
                    "exit_time": index[i],
                    "exit_price": exit_price,
                    "stop_price": stop_price,
                    "target_price": target_price,
                    "qty": qty,
                    "pnl": pnl,
                    "win": pnl > 0,
                })
                position = 0
                qty = 0.0

        if position == 0 and signals[i] != 0 and pd.notna(atrs[i]) and atrs[i] > 0:
            direction = int(signals[i])
            entry_price = price
            entry_time = index[i]
            stop_dist = atrs[i] * stop_mult
            stop_price = entry_price - direction * stop_dist
            target_price = entry_price + direction * atrs[i] * target_mult
            risk_amount = equity * (risk_pct / 100)
            qty = risk_amount / stop_dist if stop_dist > 0 else 0.0
            position = direction

        open_pnl = (price - entry_price) * qty * position if position != 0 else 0.0
        equity_curve.append(equity + open_pnl)

    open_position = None
    if position != 0:
        # posizione ancora aperta sull'ultima barra — usato dal monitor live (monitor.py) per
        # sapere se c'è un trade in corso adesso, che qui non compare mai tra i `trades` chiusi
        open_position = {
            "direction": "long" if position == 1 else "short",
            "entry_time": entry_time,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "target_price": target_price,
            "qty": qty,
        }

    result = data.copy()
    result["equity"] = equity_curve
    return result, pd.DataFrame(trades), open_position


def buy_and_hold(data: pd.DataFrame, capital: float = None) -> pd.DataFrame:
    """Benchmark: compra alla prima barra e tiene fino alla fine, stesso capitale iniziale
    della strategia — per capire quanto della performance è "solo" il mercato che sale."""
    capital = capital if capital is not None else config.INITIAL_CAPITAL
    closes = data["Close"].to_numpy()
    qty = capital / closes[0]

    result = data.copy()
    result["equity"] = qty * closes
    return result
