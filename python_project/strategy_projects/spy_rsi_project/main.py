"""Entry point: carica, ottimizza, backtesta, plotta."""

import config
from data.data_loader import load_data
from strategies.rsi_strategy import rsi_strategy
from backtest.engine import backtest
from optimization.optimizer import optimize
from utils.metrics import sharpe_ratio, max_drawdown, total_return
from utils.plot import plot_equity


def main():
    symbol = config.SYMBOLS[0]
    data = load_data(symbol, config.INTERVAL)

    print("Ottimizzazione parametri RSI...")
    results = optimize(
        data,
        config.INITIAL_CAPITAL,
        config.RISK_PER_TRADE,
        config.RSI_PERIOD_RANGE,
        config.OVERSOLD_RANGE,
        config.OVERBOUGHT_RANGE,
    )
    best = results.iloc[0]
    print(f"Miglior combo: period={best['period']}, oversold={best['oversold']}, overbought={best['overbought']}, return={best['return']:.2%}")

    strat = rsi_strategy(data, int(best["period"]), int(best["oversold"]), int(best["overbought"]))
    bt = backtest(strat, config.INITIAL_CAPITAL, config.RISK_PER_TRADE)
    eq = bt["equity"].values

    print(f"Total Return: {total_return(eq):.2%}")
    print(f"Sharpe Ratio: {sharpe_ratio(eq):.2f}")
    print(f"Max Drawdown: {max_drawdown(eq):.2%}")

    results.to_csv("results_rsi_optimization.csv", index=False)
    plot_equity(bt, title=f"SPY RSI({int(best['period'])}) | OS={int(best['oversold'])} OB={int(best['overbought'])}")


if __name__ == "__main__":
    main()
