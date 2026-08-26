def backtest(data, initial_capital=10000, risk_per_trade=0.05):
    df = data.copy()

    capital = initial_capital
    equity = []

    df['returns'] = df['Close'].pct_change()

    for i in range(len(df)):
        if i == 0:
            equity.append(capital)
            continue

        signal = df['signal'].iloc[i-1]
        ret = df['returns'].iloc[i]

        # 👉 rischio percentuale
        trade_return = signal * ret * risk_per_trade

        capital = capital * (1 + trade_return)
        equity.append(capital)

    df['equity'] = equity

    total_return = capital - initial_capital

    return df, total_return