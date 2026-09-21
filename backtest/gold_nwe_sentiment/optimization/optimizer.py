"""Grid search sui parametri della banda NWE, la soglia di veto sentiment e gli stop/target
ATR — e confronto tra le varianti di filtro di entrata (config.VARIANTS).

La banda NWE viene ricalcolata solo per (bandwidth, multiplier) — i filtri (sentiment,
conferma, trend) vengono riapplicati a costo quasi nullo, senza rifare il calcolo pesante
della banda.
"""

import itertools

import pandas as pd

import config
from backtest.engine import backtest
from strategies.nwe_sentiment_strategy import apply_entry_filters, attach_sentiment, build_bands
from utils.metrics import max_drawdown, sharpe_ratio, total_return


def optimize(
    data,
    sentiment,
    capital: float,
    risk_pct: float,
    periods_per_year: float = 252,
    bandwidth_range=None,
    multiplier_range=None,
    veto_range=None,
    stop_range=None,
    target_range=None,
    min_trades: int = None,
    use_confirmation: bool = False,
    use_trend_filter: bool = False,
) -> pd.DataFrame:
    """Ritorna DataFrame con tutte le combinazioni valide, ordinate per Sharpe decrescente."""
    bandwidth_range = bandwidth_range or config.BANDWIDTH_RANGE
    multiplier_range = multiplier_range or config.MULTIPLIER_RANGE
    veto_range = veto_range or config.SENTIMENT_VETO_RANGE
    stop_range = stop_range or config.ATR_STOP_RANGE
    target_range = target_range or config.ATR_TARGET_RANGE
    min_trades = min_trades if min_trades is not None else config.MIN_TRADES

    results = []
    for bandwidth, multiplier in itertools.product(bandwidth_range, multiplier_range):
        bands = build_bands(data, bandwidth=bandwidth, multiplier=multiplier)
        with_sentiment = attach_sentiment(bands, sentiment)

        for veto in veto_range:
            signals = apply_entry_filters(
                with_sentiment, sentiment_veto=veto,
                use_confirmation=use_confirmation, use_trend_filter=use_trend_filter,
            )

            for stop_mult, target_mult in itertools.product(stop_range, target_range):
                bt, trades = backtest(signals, capital, risk_pct, stop_mult, target_mult)
                if len(trades) < min_trades:
                    continue
                eq = bt["equity"].to_numpy()
                results.append({
                    "bandwidth": bandwidth,
                    "multiplier": multiplier,
                    "sentiment_veto": veto,
                    "atr_stop": stop_mult,
                    "atr_target": target_mult,
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


def compare_variants(
    data,
    sentiment,
    capital: float,
    risk_pct: float,
    periods_per_year: float = 252,
    variants: list[dict] = None,
    **optimize_kwargs,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lancia optimize() per ogni variante di config.VARIANTS.

    Ritorna (summary, full): summary ha una riga per variante con la sua combinazione
    migliore (Sharpe più alto); full ha tutte le combinazioni di tutte le varianti,
    con una colonna 'variant' per poterle confrontare/esportare.
    """
    variants = variants or config.VARIANTS

    all_results = []
    summary_rows = []

    for variant in variants:
        df = optimize(
            data, sentiment, capital, risk_pct, periods_per_year,
            use_confirmation=variant["use_confirmation"],
            use_trend_filter=variant["use_trend_filter"],
            **optimize_kwargs,
        )
        if df.empty:
            summary_rows.append({"variant": variant["name"], "trades": 0})
            continue

        df = df.copy()
        df.insert(0, "variant", variant["name"])
        all_results.append(df)
        summary_rows.append({"variant": variant["name"], **df.iloc[0].drop("variant").to_dict()})

    full = pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    return summary, full
