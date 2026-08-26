import yfinance as yf
df = yf.download("020Y.L", period="1mo", interval="1d", auto_adjust=False)
print(df.head())
print(df.columns)