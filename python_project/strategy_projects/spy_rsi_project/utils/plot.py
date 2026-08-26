"""Grafico equity curve."""

import matplotlib.pyplot as plt


def plot_equity(data, title: str = "Equity Curve"):
    """Mostra equity curve."""
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(data.index, data["equity"], label="Equity")
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Capital ($)")
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    plt.savefig("equity_curve.png")
    plt.show()
