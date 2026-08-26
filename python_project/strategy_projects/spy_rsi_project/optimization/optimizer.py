"""Grid search sui parametri RSI."""

import itertools
import pandas as pd
from strategies.rsi_strategy import rsi_strategy
from backtest.engine import backtest
from utils.metrics import total_return


def optimize(data, capital: float, risk: float, period_range, oversold_range, overbought_range):
    """Ritorna DataFrame con tutte le combinazioni ordinate per rendimento."""
    results = []
    for period, oversold, overbought in itertools.product(period_range, oversold_range, overbought_range):
        if oversold >= overbought:
            continue
        strat = rsi_strategy(data, period, oversold, overbought)
        bt = backtest(strat, capital, risk)
        ret = total_return(bt["equity"].values)
        results.append({
            "period": period,
            "oversold": oversold,
            "overbought": overbought,
            "return": ret,
        })
    df = pd.DataFrame(results)
    df.sort_values("return", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df
