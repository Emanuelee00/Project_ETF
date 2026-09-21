"""Monitor live: ogni MONITOR_INTERVAL_SECONDS (default 60s) controlla se la configurazione
vincente calcolata dall'ultimo 'make gold-nwe' (best_strategy_config.json) ha aperto o chiuso
un trade, e lo notifica su Telegram con i livelli di entry/stop/target.

Lancio: make monitor (Ctrl+C per fermare). Richiede TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID
in un file .env in questa cartella (vedi .env.example).

Nota: usa la stessa banda NWE e lo stesso filtro sentiment del backtest, ma il sentiment
resta comunque un segnale giornaliero — non cambia infrabar.
"""

import argparse
import json
import time
from pathlib import Path

import requests

import config
from backtest.engine import backtest
from data.data_loader import load_daily_sentiment, load_price_data
from strategies.nwe_sentiment_strategy import build_signals

STATE_PATH = Path(config.MONITOR_STATE_PATH)


def _load_best_config() -> dict:
    path = Path(config.BEST_STRATEGY_CONFIG_PATH)
    if not path.exists():
        raise SystemExit(f"{path} non trovato — lancia prima 'make run' (main.py) per calcolare la configurazione migliore")
    return json.loads(path.read_text())


def _load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"open_entry_time": None}


def _save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state))


def _send_telegram(message: str) -> None:
    token, chat_id = config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        print("[monitor] TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID non configurati (vedi .env.example) — salto invio")
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as exc:
        print(f"[monitor] invio Telegram fallito: {exc}")


def check_once(best: dict, state: dict, capital: float = None) -> dict:
    capital = capital if capital is not None else config.INITIAL_CAPITAL

    data = load_price_data(period=config.MONITOR_REFRESH_PERIOD)
    sentiment = load_daily_sentiment()

    signals = build_signals(
        data, sentiment,
        bandwidth=best["bandwidth"], multiplier=best["multiplier"], sentiment_veto=best["sentiment_veto"],
        use_confirmation=best["use_confirmation"], use_trend_filter=best["use_trend_filter"],
    )
    bt, trades, open_position = backtest(
        signals, capital, config.RISK_PER_TRADE, best["atr_stop"], best["atr_target"],
    )

    current_entry = open_position["entry_time"].isoformat() if open_position else None
    previous_entry = state.get("open_entry_time")

    if current_entry and current_entry != previous_entry:
        direction_it = "LONG (compra)" if open_position["direction"] == "long" else "SHORT (vendi)"
        msg = (
            f"🥇 Nuovo segnale oro — {direction_it}\n"
            f"Entrata: ${open_position['entry_price']:.2f} ({open_position['entry_time']:%Y-%m-%d %H:%M})\n"
            f"Stop loss: ${open_position['stop_price']:.2f}\n"
            f"Take profit: ${open_position['target_price']:.2f}"
        )
        print(msg)
        _send_telegram(msg)
        state["open_entry_time"] = current_entry

    elif not current_entry and previous_entry:
        last = trades.iloc[-1] if not trades.empty else None
        if last is not None and last["entry_time"].isoformat() == previous_entry:
            esito = "in profitto ✅" if last["win"] else "in perdita ❌"
            msg = (
                f"🥇 Trade oro chiuso — {esito}\n"
                f"Uscita: ${last['exit_price']:.2f} ({last['exit_time']:%Y-%m-%d %H:%M})\n"
                f"P&L: ${last['pnl']:.2f}"
            )
            print(msg)
            _send_telegram(msg)
        state["open_entry_time"] = None

    _save_state(state)
    return state


def main():
    parser = argparse.ArgumentParser(description="Monitor live: notifica su Telegram i trade della strategia NWE + sentiment")
    parser.add_argument("--capital", type=float, default=config.INITIAL_CAPITAL, help="Capitale usato per calcolare quantità/P&L (default: config.INITIAL_CAPITAL)")
    args = parser.parse_args()

    best = _load_best_config()
    state = _load_state()
    print(f"Monitor avviato (variante '{best['variant']}', capitale ${args.capital:,.2f}) — controllo ogni {config.MONITOR_INTERVAL_SECONDS}s. Ctrl+C per fermare.")

    while True:
        try:
            state = check_once(best, state, args.capital)
        except Exception as exc:
            print(f"[monitor] errore durante il controllo: {exc}")
        time.sleep(config.MONITOR_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
