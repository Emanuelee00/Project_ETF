"""Entry point: confronta le varianti della strategia NWE (no-repaint) + sentiment sull'oro
— baseline, candela di conferma/rifiuto, filtro di trend e le due insieme — poi mostra il
dettaglio della migliore contro il benchmark buy & hold.

Se run_nwe_grid_search.py è già stato lanciato (best_nwe_params.json presente), usa il
bandwidth/multiplier trovati lì dalla grid search fine (passo 0.1) invece della griglia
rada di config.BANDWIDTH_RANGE/MULTIPLIER_RANGE.
"""

import json
from pathlib import Path

import config
from backtest.engine import backtest, buy_and_hold
from data.data_loader import load_daily_sentiment, load_price_data
from optimization.optimizer import compare_variants
from strategies.nwe_sentiment_strategy import build_signals
from utils.export import export_sentiment_json, export_trades_json
from utils.metrics import max_drawdown, sharpe_ratio, total_return
from utils.plot import plot_strategy


def _ask_capital(default: float) -> float:
    raw = input(f"Capitale iniziale in $ [invio per {default:,.0f}]: ").strip()
    if not raw:
        return default
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        print(f"Valore non valido, uso il default {default:,.0f}")
        return default


def main():
    capital = _ask_capital(config.INITIAL_CAPITAL)

    data = load_price_data()
    sentiment = load_daily_sentiment()
    print(f"Barre scaricate: {len(data)} | giorni con sentiment salvato: {len(sentiment)}")
    print(f"Periodo dati: {data.index[0]:%Y-%m-%d %H:%M} → {data.index[-1]:%Y-%m-%d %H:%M}")

    unique_days = data.index.strftime("%Y-%m-%d").nunique()
    periods_per_year = (len(data) / unique_days) * 252 if unique_days else 252

    bandwidth_range, multiplier_range = config.BANDWIDTH_RANGE, config.MULTIPLIER_RANGE
    best_params_path = Path(config.BEST_NWE_PARAMS_PATH)
    if best_params_path.exists():
        best_nwe = json.loads(best_params_path.read_text())
        bandwidth_range, multiplier_range = [best_nwe["bandwidth"]], [best_nwe["multiplier"]]
        print(f"Uso bandwidth={best_nwe['bandwidth']}, multiplier={best_nwe['multiplier']} da {best_params_path} (grid search fine)")
    else:
        print(f"{best_params_path} non trovato — uso la griglia rada di config.py (lancia prima run_nwe_grid_search.py per una migliore)")

    print("Confronto varianti (baseline / candela di conferma / filtro trend / entrambe)...")
    summary, full = compare_variants(
        data, sentiment, capital, config.RISK_PER_TRADE, periods_per_year,
        bandwidth_range=bandwidth_range, multiplier_range=multiplier_range,
    )

    if summary.empty or "sharpe" not in summary.columns or summary["sharpe"].isna().all():
        print(f"Nessuna variante ha trovato almeno {config.MIN_TRADES} trade — allarga il periodo o abbassa MIN_TRADES.")
        return

    print()
    cols = [
        "variant", "bandwidth", "multiplier", "sentiment_veto", "atr_stop", "atr_target",
        "trades", "win_rate", "return", "sharpe", "max_drawdown",
    ]
    print(summary[cols].to_string(
        index=False,
        formatters={
            "win_rate": lambda v: f"{v:.1%}" if v == v else "—",
            "return": lambda v: f"{v:.2%}" if v == v else "—",
            "sharpe": lambda v: f"{v:.2f}" if v == v else "—",
            "max_drawdown": lambda v: f"{v:.2%}" if v == v else "—",
        },
    ))

    if not full.empty:
        full.to_csv("results_variants_comparison.csv", index=False)
        print("Tutte le combinazioni di tutte le varianti esportate in results_variants_comparison.csv")

    best = summary.loc[summary["sharpe"].idxmax()]
    best_variant = next(v for v in config.VARIANTS if v["name"] == best["variant"])
    print(f"\nMigliore variante: '{best['variant']}' (Sharpe {best['sharpe']:.2f})")

    signals = build_signals(
        data, sentiment,
        bandwidth=best["bandwidth"], multiplier=best["multiplier"], sentiment_veto=best["sentiment_veto"],
        use_confirmation=best_variant["use_confirmation"], use_trend_filter=best_variant["use_trend_filter"],
    )
    bt, trades, _ = backtest(signals, capital, config.RISK_PER_TRADE, best["atr_stop"], best["atr_target"])
    eq = bt["equity"].to_numpy()

    bh = buy_and_hold(data, capital)
    bt["equity_bh"] = bh["equity"].to_numpy()
    eq_bh = bt["equity_bh"].to_numpy()

    print()
    print(f"Periodo backtest: {data.index[0]:%Y-%m-%d %H:%M} → {data.index[-1]:%Y-%m-%d %H:%M}")
    print(f"Capitale iniziale: ${capital:,.2f}")
    print()
    print(f"{'':22}{'Strategia':>16}{'Buy & Hold':>16}")
    print(f"{'Capitale finale':22}${eq[-1]:>14,.2f} ${eq_bh[-1]:>14,.2f}")
    print(f"{'Total Return':22}{total_return(eq):>15.2%} {total_return(eq_bh):>15.2%}")
    print(f"{'Sharpe Ratio':22}{sharpe_ratio(eq, periods_per_year):>16.2f}{sharpe_ratio(eq_bh, periods_per_year):>16.2f}")
    print(f"{'Max Drawdown':22}{max_drawdown(eq):>15.2%} {max_drawdown(eq_bh):>15.2%}")
    print(f"Numero trade: {len(trades)}")

    json_path = export_sentiment_json(bt)
    print(f"Serie sentiment (score + etichetta per barra) esportata in {json_path}")

    trades_path = export_trades_json(trades)
    print(f"{len(trades)} trade esportati in {trades_path} — il sito li legge da lì, senza ricalcolare nulla")

    best_config = {
        "bandwidth": float(best["bandwidth"]),
        "multiplier": float(best["multiplier"]),
        "sentiment_veto": float(best["sentiment_veto"]),
        "atr_stop": float(best["atr_stop"]),
        "atr_target": float(best["atr_target"]),
        "use_confirmation": best_variant["use_confirmation"],
        "use_trend_filter": best_variant["use_trend_filter"],
        "variant": best["variant"],
    }
    with open(config.BEST_STRATEGY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(best_config, f, indent=2)
    print(f"Configurazione completa della strategia migliore salvata in {config.BEST_STRATEGY_CONFIG_PATH} (usata da 'make monitor')")

    plot_strategy(
        bt,
        sentiment_veto=best["sentiment_veto"],
        title=(
            f"GC=F — variante '{best['variant']}' | h={best['bandwidth']} m={best['multiplier']} "
            f"veto=±{best['sentiment_veto']} stop={best['atr_stop']} target={best['atr_target']}"
        ),
    )


if __name__ == "__main__":
    main()
