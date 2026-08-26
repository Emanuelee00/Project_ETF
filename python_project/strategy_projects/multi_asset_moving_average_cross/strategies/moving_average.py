def moving_average_strategy(data, short_window, long_window):
    df = data.copy()

    df['short_ma'] = df['Close'].rolling(short_window).mean()
    df['long_ma'] = df['Close'].rolling(long_window).mean()

    df['signal'] = 0
    df.loc[df.index[short_window:], 'signal'] = (
        df['short_ma'][short_window:] > df['long_ma'][short_window:]
    ).astype(int)

    return df