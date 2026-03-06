import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

from analytics import fetch_prices

TRADING_DAYS = 252

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    layout="wide",
    page_title="Quant Terminal",
    page_icon="📈"
)

st.title("📈 Quant Trading Terminal")

# =========================================================
# PATH CONFIG (compatibile con tua struttura)
# =========================================================

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
MAPPING_FILE = DATA_DIR / "isin_ticker_mapping.csv"

# =========================================================
# LOAD TICKER UNIVERSE
# =========================================================

mapping_df = pd.read_csv(MAPPING_FILE)
mapping_df.columns = mapping_df.columns.str.strip()
mapping_df = mapping_df[["Ticker"]].dropna()
tickers = sorted(mapping_df["Ticker"].unique())

# =========================================================
# READ TICKER FROM URL (Excel integration)
# =========================================================

query_params = st.query_params
ticker_from_url = query_params.get("ticker", None)

# =========================================================
# SIDEBAR CONTROLS
# =========================================================

st.sidebar.header("Market")

search = st.sidebar.text_input("Search Ticker")

if search:
    tickers_filtered = [t for t in tickers if search.upper() in t]
else:
    tickers_filtered = tickers

if ticker_from_url and ticker_from_url in tickers_filtered:
    default_index = tickers_filtered.index(ticker_from_url)
else:
    default_index = 0

ticker = st.sidebar.selectbox(
    "Select Asset",
    tickers_filtered,
    index=default_index
)

years = st.sidebar.slider("Years of History", 1, 15, 5)

# ---------------- THEME SELECTION ----------------

theme = st.sidebar.selectbox(
    "Chart Theme",
    ["TradingView Dark", "TradingView Light", "Dark", "Light"]
)

if theme == "TradingView Dark":
    template = "plotly_dark"
    bg_color = "#131722"
elif theme == "TradingView Light":
    template = "plotly_white"
    bg_color = "#ffffff"
elif theme == "Dark":
    template = "plotly_dark"
    bg_color = "#000000"
else:
    template = "plotly_white"
    bg_color = "#ffffff"

# ---------------- INDICATORS ----------------

st.sidebar.header("Indicators")

ma_short = st.sidebar.number_input("MA Short", 5, 100, 50)
ma_long = st.sidebar.number_input("MA Long", 50, 300, 200)

show_rsi = st.sidebar.checkbox("Show RSI", True)
show_macd = st.sidebar.checkbox("Show MACD", False)

# =========================================================
# LOAD DATA
# =========================================================

@st.cache_data
def load_data(t):
    return fetch_prices([t])

prices_raw = load_data(ticker)

if prices_raw.empty:
    st.stop()

prices_raw = prices_raw.tail(years * TRADING_DAYS)

# Se non abbiamo OHLC veri
if {"Open", "High", "Low", "Close"}.issubset(prices_raw.columns):
    prices = prices_raw.copy()
else:
    close = prices_raw[ticker]
    prices = pd.DataFrame(index=close.index)
    prices["Open"] = close.shift(1)
    prices["High"] = close * 1.01
    prices["Low"] = close * 0.99
    prices["Close"] = close

# =========================================================
# INDICATORS CALCULATION
# =========================================================

prices["MA_SHORT"] = prices["Close"].rolling(ma_short).mean()
prices["MA_LONG"] = prices["Close"].rolling(ma_long).mean()

returns = prices["Close"].pct_change()

# RSI
delta = returns
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)
avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()
rs = avg_gain / avg_loss
rsi = 100 - (100 / (1 + rs))

# MACD
ema12 = prices["Close"].ewm(span=12).mean()
ema26 = prices["Close"].ewm(span=26).mean()
macd = ema12 - ema26
signal = macd.ewm(span=9).mean()

volume = prices["Close"].pct_change().abs() * 1_000_000

# =========================================================
# SUBPLOTS (TradingView Style)
# =========================================================

rows = 3 if show_rsi or show_macd else 2

fig = make_subplots(
    rows=rows,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.02,
    row_heights=[0.6, 0.2, 0.2] if rows == 3 else [0.7, 0.3]
)

# ---------------- PRICE ----------------

fig.add_trace(
    go.Candlestick(
        x=prices.index,
        open=prices["Open"],
        high=prices["High"],
        low=prices["Low"],
        close=prices["Close"],
        name="Price"
    ),
    row=1, col=1
)

fig.add_trace(
    go.Scatter(
        x=prices.index,
        y=prices["MA_SHORT"],
        name=f"MA {ma_short}",
        line=dict(width=1)
    ),
    row=1, col=1
)

fig.add_trace(
    go.Scatter(
        x=prices.index,
        y=prices["MA_LONG"],
        name=f"MA {ma_long}",
        line=dict(width=1)
    ),
    row=1, col=1
)

# ---------------- VOLUME ----------------

fig.add_trace(
    go.Bar(
        x=prices.index,
        y=volume,
        name="Volume"
    ),
    row=2, col=1
)

# ---------------- RSI / MACD ----------------

if rows == 3:
    if show_rsi:
        fig.add_trace(
            go.Scatter(
                x=prices.index,
                y=rsi,
                name="RSI"
            ),
            row=3, col=1
        )
        fig.add_hline(y=70, row=3, col=1)
        fig.add_hline(y=30, row=3, col=1)

    if show_macd:
        fig.add_trace(
            go.Scatter(
                x=prices.index,
                y=macd,
                name="MACD"
            ),
            row=3, col=1
        )
        fig.add_trace(
            go.Scatter(
                x=prices.index,
                y=signal,
                name="Signal"
            ),
            row=3, col=1
        )

# =========================================================
# LAYOUT SETTINGS
# =========================================================

fig.update_layout(
    template=template,
    height=900,
    dragmode="zoom",
    hovermode="x unified",
    paper_bgcolor=bg_color,
    plot_bgcolor=bg_color,
    xaxis=dict(
        rangeslider=dict(visible=True),
        type="date"
    ),
    showlegend=True
)

st.plotly_chart(
    fig,
    use_container_width=True,
    config={
        "scrollZoom": True,
        "displayModeBar": True,
        "displaylogo": False,
        "modeBarButtonsToAdd": [
            "zoom2d",
            "pan2d",
            "select2d",
            "lasso2d",
            "zoomIn2d",
            "zoomOut2d",
            "autoScale2d",
            "resetScale2d"
        ]
    }
)

st.caption("Quant Trading Terminal • Professional Edition - Emanuele ielmini - @copyright")