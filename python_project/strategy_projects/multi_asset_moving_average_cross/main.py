from data.data_loader import load_data
from optimization.optimizer import optimize
from strategies.moving_average import moving_average_strategy
from backtest.engine import backtest
from utils.plot import plot_equity
from config import *
from tqdm import tqdm
import pandas as pd

def main():
    
    all_results = []

    short_range = range(5, 30, 5)
    long_range = range(20, 100, 10)

    print("\n🚀 Avvio backtest multi-asset...\n")

    for symbol in tqdm(SYMBOLS, desc="Simboli"):  # ✅ FIX QUI
        try:
            data = load_data(symbol, interval=INTERVAL)

            if data is None or len(data) < 50:
                continue

            results = optimize(data, short_range, long_range)

            best = results[0]

            all_results.append({
                "symbol": symbol,
                "best_short": best["short"],
                "best_long": best["long"],
                "return": best["return"]
            })

        except Exception as e:
            print(f"Errore su {symbol}: {e}")

    # 📊 DataFrame risultati
    df = pd.DataFrame(all_results)
    df = df.sort_values(by="return", ascending=False).reset_index(drop=True)

    print("\n🏆 MIGLIORI STRATEGIE PER SIMBOLO:\n")
    print(df)

    # 💾 salva CSV
    df.to_csv("results_multi_asset.csv", index=False)
    print("\n💾 Salvato in results_multi_asset.csv")

    # 🔥 EQUITY CURVE sul migliore
    if len(df) > 0:
        best_symbol = df.iloc[0]["symbol"]
        best_short = df.iloc[0]["best_short"]
        best_long = df.iloc[0]["best_long"]

        print(f"\n📈 Plot migliore: {best_symbol} ({best_short}/{best_long})")

        data = load_data(best_symbol, interval=INTERVAL)

        strat = moving_average_strategy(data, best_short, best_long)

        df_bt, _ = backtest(
            strat,
            initial_capital=INITIAL_CAPITAL,
            risk_per_trade=RISK_PER_TRADE
        )

        plot_equity(df_bt, title=f"{best_symbol} Equity Curve")


if __name__ == "__main__":
    main()