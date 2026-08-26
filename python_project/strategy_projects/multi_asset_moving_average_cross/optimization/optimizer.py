from itertools import product
from strategies.moving_average import moving_average_strategy
from backtest.engine import backtest
from tqdm import tqdm
from config import INITIAL_CAPITAL, RISK_PER_TRADE

def optimize(data, short_range, long_range):
    results = []

    combinations = list(product(short_range, long_range))

    for short, long in tqdm(combinations, desc="Combinazioni", leave=False):
        if short >= long:
            continue
        
        strat = moving_average_strategy(data, short, long)
        _, total_return = backtest(
            strat,
            initial_capital=INITIAL_CAPITAL,
            risk_per_trade=RISK_PER_TRADE
        )
        
        results.append({
            "short": short,
            "long": long,
            "return": total_return
        })

    results.sort(key=lambda x: x['return'], reverse=True)
    return results