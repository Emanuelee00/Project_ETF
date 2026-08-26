# data/data_loader.py

import yfinance as yf

def load_data(symbol, start=None, end=None, interval="1d"):
    
    if interval == "1d":
        data = yf.download(symbol, start=start, end=end)
    else:
        # intraday usa "period"
        data = yf.download(symbol, period="7d", interval=interval)

    data = data[['Close']].dropna()
    return data