"""Entry point: grid search fine (passo 0.1) sulla sola banda NWE, per trovare i parametri
migliori da passare poi a main.py (strategia completa con sentiment + benchmark).

Salva:
- results_nwe_grid_search.csv — tutte le combinazioni valide (di solito qualche migliaio)
- best_nwe_params.json — la combinazione migliore, che main.py legge automaticamente al
  posto della griglia rada di config.BANDWIDTH_RANGE/MULTIPLIER_RANGE
"""

import json
import time

import config
from data.data_loader import load_price_data
from strategies.nwe_grid_search import run_grid_search


def main():
    data = load_price_data()
    print(f"Barre scaricate (storico accumulato in cache): {len(data)}")

    unique_days = data.index.strftime("%Y-%m-%d").nunique()
    periods_per_year = (len(data) / unique_days) * 252 if unique_days else 252

    n_bw = len(config.FINE_BANDWIDTH_RANGE)
    n_mult = len(config.FINE_MULTIPLIER_RANGE)
    print(f"Grid search: {n_bw} bandwidth x {n_mult} multiplier = {n_bw * n_mult} combinazioni...")

    start = time.time()
    results = run_grid_search(data, config.INITIAL_CAPITAL, config.RISK_PER_TRADE, periods_per_year)
    elapsed = time.time() - start
    print(f"Completato in {elapsed:.1f}s — {len(results)} combinazioni con almeno {config.MIN_TRADES} trade")

    if results.empty:
        print("Nessuna combinazione valida — allarga lo storico (rilancia più volte per far crescere la cache) o abbassa MIN_TRADES.")
        return

    results.to_csv("results_nwe_grid_search.csv", index=False)
    print("Tutte le combinazioni salvate in results_nwe_grid_search.csv")

    best = results.iloc[0]
    print(
        f"\nMigliore: bandwidth={best['bandwidth']}, multiplier={best['multiplier']}, "
        f"trade={int(best['trades'])}, win_rate={best['win_rate']:.1%}, "
        f"return={best['return']:.2%}, sharpe={best['sharpe']:.2f}, max_drawdown={best['max_drawdown']:.2%}"
    )

    print("\nTop 10:")
    print(results.head(10).to_string(index=False))

    with open(config.BEST_NWE_PARAMS_PATH, "w", encoding="utf-8") as f:
        json.dump({"bandwidth": float(best["bandwidth"]), "multiplier": float(best["multiplier"])}, f, indent=2)
    print(f"\nParametri migliori salvati in {config.BEST_NWE_PARAMS_PATH} — 'make run' li userà automaticamente.")


if __name__ == "__main__":
    main()
