"""Grafici: equity curve semplice, e vista completa prezzo+banda+trade / sentiment / equity."""

import matplotlib.pyplot as plt


def plot_equity(data, title: str = "Equity Curve"):
    """Solo equity curve."""
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(data.index, data["equity"], label="Equity")
    ax.set_title(title)
    ax.set_xlabel("Data")
    ax.set_ylabel("Capitale ($)")
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    plt.savefig("equity_curve.png")
    plt.show()


def plot_strategy(data, sentiment_veto: float, title: str = "GC=F — NWE + Sentiment", out_path: str = "strategy_overview.png"):
    """Tre pannelli allineati sul tempo: prezzo+banda+trade, sentiment con soglie di veto, equity."""
    fig, (ax_price, ax_sent, ax_eq) = plt.subplots(
        3, 1, figsize=(12, 9), sharex=True, gridspec_kw={"height_ratios": [2.5, 1, 1.5]}
    )

    ax_price.plot(data.index, data["Close"], color="#1f77b4", linewidth=0.8, label="Close")
    ax_price.plot(data.index, data["nwe_line"], color="#f59e0b", linewidth=0.8, label="NWE")
    ax_price.plot(data.index, data["nwe_upper"], color="#94a3b8", linewidth=0.6, linestyle="--")
    ax_price.plot(data.index, data["nwe_lower"], color="#94a3b8", linewidth=0.6, linestyle="--")
    longs = data[data["signal"] == 1]
    shorts = data[data["signal"] == -1]
    ax_price.scatter(longs.index, longs["Close"], color="#10b981", marker="^", s=30, label="Long", zorder=5)
    ax_price.scatter(shorts.index, shorts["Close"], color="#ef4444", marker="v", s=30, label="Short", zorder=5)
    ax_price.set_ylabel("Prezzo")
    ax_price.legend(loc="upper left", fontsize=8)
    ax_price.set_title(title)
    ax_price.grid(True, alpha=0.3)

    ax_sent.plot(data.index, data["sentiment_score"], color="#a78bfa", linewidth=1, label="Sentiment score")
    ax_sent.axhline(sentiment_veto, color="#10b981", linestyle=":", linewidth=1, label=f"veto long sotto -{sentiment_veto}")
    ax_sent.axhline(-sentiment_veto, color="#ef4444", linestyle=":", linewidth=1, label=f"veto short sopra +{sentiment_veto}")
    ax_sent.axhline(0, color="#475569", linewidth=0.5)
    ax_sent.set_ylabel("Sentiment")
    ax_sent.legend(loc="upper left", fontsize=7)
    ax_sent.grid(True, alpha=0.3)

    ax_eq.plot(data.index, data["equity"], color="#22c55e", linewidth=1, label="Strategia")
    if "equity_bh" in data.columns:
        ax_eq.plot(data.index, data["equity_bh"], color="#64748b", linewidth=1, linestyle="--", label="Buy & Hold")
    ax_eq.set_ylabel("Capitale ($)")
    ax_eq.set_xlabel("Data")
    ax_eq.legend(loc="upper left", fontsize=8)
    ax_eq.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path)
    plt.show()
