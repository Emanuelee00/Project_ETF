"""Streamlit web app — full ETF pipeline + space theme."""

import json
import sys
import random
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit.components.v1 as components
from pathlib import Path
from datetime import datetime

# ── ensure src/ is importable ────────────────────────────────────────────────
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from chart_backend import start_chart_server
from analytics import fetch_prices, compute_metrics as _full_metrics, validate_data_quality
from risk_metrics import compute_volatility, compute_sharpe, compute_beta, compute_max_drawdown
from optimization import optimize_portfolios
from seasonality import compute_weekly_seasonality_multi
from excel_export import export_to_excel

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="ETF Portfolio Analyzer", page_icon="📊")

BASE_DIR   = SRC_DIR.parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
FRONTEND_DIR       = SRC_DIR / "frontend"
CHART_HTML_TEMPLATE = (FRONTEND_DIR / "chart_modal.html").read_text(encoding="utf-8")
CHART_JS            = (FRONTEND_DIR / "chart_modal.js").read_text(encoding="utf-8")
CHART_API_BASE      = start_chart_server()

# ── session state ─────────────────────────────────────────────────────────────
for _k, _v in {
    "download_report_path": None,
    "download_report_name": None,
    "download_report_bytes": None,
    "selected_chart_ticker": None,
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ═══════════════════════════════════════════════════════════════════════════════
# SPACE THEME  (CSS + starfield)
# ═══════════════════════════════════════════════════════════════════════════════

_r = random.Random(42)
_ss = ", ".join(f"{_r.randint(0,2560)}px {_r.randint(0,1440)}px #fff" for _ in range(220))
_sm = ", ".join(f"{_r.randint(0,2560)}px {_r.randint(0,1440)}px #fff" for _ in range(90))
_sl = ", ".join(f"{_r.randint(0,2560)}px {_r.randint(0,1440)}px #fff" for _ in range(35))

st.markdown(f"""
<style>
/* ── Reset & base ────────────────────────────────────────────── */
html, body, .stApp {{
    background: #020509 !important;
    color: #e2e8f0 !important;
    font-family: "Segoe UI", system-ui, sans-serif !important;
}}

/* ── Starfield layers ────────────────────────────────────────── */
#st-s, #st-m, #st-l {{
    position: fixed; top: 0; left: 0;
    background: transparent;
    pointer-events: none; z-index: 0;
}}
#st-s {{ width:1px; height:1px; box-shadow:{_ss}; animation: mvS  80s linear infinite; opacity:.8; }}
#st-m {{ width:2px; height:2px; box-shadow:{_sm}; animation: mvS 120s linear infinite; opacity:.6; }}
#st-l {{ width:3px; height:3px; box-shadow:{_sl}; animation: mvS 200s linear infinite; opacity:.5; }}
@keyframes mvS {{ from {{ transform:translateY(0); }} to {{ transform:translateY(-1440px); }} }}

/* ── Nebula overlay ──────────────────────────────────────────── */
.stApp::before {{
    content: '';
    position: fixed; top:0; left:0; width:100%; height:100%;
    pointer-events: none; z-index: 0;
    background:
        radial-gradient(ellipse at 15% 65%, rgba(75,20,140,.30) 0%, transparent 52%),
        radial-gradient(ellipse at 85% 15%, rgba(0,80,180,.25)  0%, transparent 52%),
        radial-gradient(ellipse at 55% 85%, rgba(0,160,210,.13) 0%, transparent 48%),
        radial-gradient(ellipse at 40% 30%, rgba(100,0,180,.10) 0%, transparent 45%);
}}

/* ── Sidebar ─────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background: rgba(3,6,18,.94) !important;
    border-right: 1px solid rgba(0,229,255,.13) !important;
    backdrop-filter: blur(14px);
}}
[data-testid="stSidebar"] * {{ color: #b0c4de !important; }}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{ color: #00e5ff !important; text-shadow: 0 0 10px rgba(0,229,255,.4); }}

/* ── Page title ──────────────────────────────────────────────── */
h1 {{
    background: linear-gradient(120deg, #00e5ff 0%, #8b5cf6 55%, #00e5ff 100%);
    background-size: 200% auto;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    animation: shimmer 4s linear infinite;
    font-size: 2.6rem !important;
    letter-spacing: .03em;
    filter: drop-shadow(0 0 18px rgba(0,229,255,.35));
}}
@keyframes shimmer {{ to {{ background-position: 200% center; }} }}

h2 {{ color: #a5d8ff !important; border-bottom: 1px solid rgba(0,229,255,.15); padding-bottom: 6px; }}
h3 {{ color: #7ec8e3 !important; }}

/* ── Metric cards ────────────────────────────────────────────── */
[data-testid="stMetric"] {{
    background: linear-gradient(135deg, rgba(0,229,255,.06), rgba(139,92,246,.06)) !important;
    border: 1px solid rgba(0,229,255,.18) !important;
    border-radius: 16px !important;
    padding: 16px !important;
    backdrop-filter: blur(8px);
    box-shadow: 0 0 18px rgba(0,229,255,.06);
    transition: box-shadow .3s;
}}
[data-testid="stMetric"]:hover {{ box-shadow: 0 0 30px rgba(0,229,255,.15); }}
[data-testid="stMetricLabel"] {{ color: #94a3b8 !important; font-size:.82rem !important; }}
[data-testid="stMetricValue"] {{ color: #00e5ff !important; font-weight: 700 !important; font-size: 1.6rem !important; text-shadow: 0 0 12px rgba(0,229,255,.5); }}

/* ── Dataframe ───────────────────────────────────────────────── */
[data-testid="stDataFrame"] {{
    border: 1px solid rgba(0,229,255,.12) !important;
    border-radius: 14px !important;
    overflow: hidden;
    backdrop-filter: blur(6px);
}}

/* ── Tabs ────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {{
    background: rgba(0,229,255,.04);
    border-radius: 12px; padding: 4px;
    border: 1px solid rgba(0,229,255,.08);
}}
[data-testid="stTabs"] [role="tab"] {{
    color: #94a3b8 !important; border-radius: 8px; transition: all .2s;
}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    background: rgba(0,229,255,.14) !important;
    color: #00e5ff !important;
    box-shadow: 0 0 14px rgba(0,229,255,.25);
}}

/* ── Ticker buttons ──────────────────────────────────────────── */
.stButton > button {{
    background: rgba(0,229,255,.05) !important;
    border: 1px solid rgba(0,229,255,.22) !important;
    color: #a5d8ff !important;
    border-radius: 8px !important;
    font-size: .78rem !important;
    transition: all .22s !important;
}}
.stButton > button:hover {{
    background: rgba(0,229,255,.14) !important;
    border-color: #00e5ff !important;
    color: #00e5ff !important;
    box-shadow: 0 0 16px rgba(0,229,255,.35) !important;
    transform: translateY(-1px);
}}

/* ── Download button — glowing CTA ──────────────────────────── */
[data-testid="stDownloadButton"] > button {{
    background: linear-gradient(135deg, rgba(0,229,255,.14), rgba(139,92,246,.14)) !important;
    border: 1.5px solid #00e5ff !important;
    color: #00e5ff !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 1.05rem !important;
    padding: 14px 28px !important;
    letter-spacing: .04em;
    animation: glowBtn 2.6s ease-in-out infinite !important;
    transition: all .3s !important;
}}
[data-testid="stDownloadButton"] > button:hover {{
    background: linear-gradient(135deg, rgba(0,229,255,.25), rgba(139,92,246,.25)) !important;
    box-shadow: 0 0 50px rgba(0,229,255,.7), inset 0 0 30px rgba(0,229,255,.12) !important;
    transform: translateY(-3px) scale(1.02) !important;
}}
@keyframes glowBtn {{
    0%,100% {{ box-shadow: 0 0 16px rgba(0,229,255,.28), inset 0 0 14px rgba(0,229,255,.05); }}
    50%      {{ box-shadow: 0 0 40px rgba(0,229,255,.60), inset 0 0 26px rgba(0,229,255,.09); }}
}}

/* ── Progress bar ────────────────────────────────────────────── */
[data-testid="stProgress"] > div > div {{
    background: linear-gradient(90deg, #00e5ff, #8b5cf6, #00e5ff) !important;
    background-size: 200% auto !important;
    animation: progressShimmer 2s linear infinite !important;
    box-shadow: 0 0 12px rgba(0,229,255,.55) !important;
    border-radius: 4px !important;
}}
[data-testid="stProgress"] {{
    background: rgba(255,255,255,.06) !important;
    border-radius: 4px !important;
}}
@keyframes progressShimmer {{ to {{ background-position: 200% center; }} }}

/* ── Alerts / notifications ──────────────────────────────────── */
[data-baseweb="notification"] {{
    background: rgba(0,229,255,.06) !important;
    border-left: 3px solid #00e5ff !important;
    border-radius: 12px !important;
    backdrop-filter: blur(6px);
}}

/* ── File uploader ───────────────────────────────────────────── */
[data-testid="stFileUploader"] {{
    background: rgba(0,229,255,.04) !important;
    border: 1.5px dashed rgba(0,229,255,.35) !important;
    border-radius: 16px !important;
    transition: all .3s;
}}
[data-testid="stFileUploader"]:hover {{
    border-color: #00e5ff !important;
    background: rgba(0,229,255,.08) !important;
    box-shadow: 0 0 20px rgba(0,229,255,.15);
}}

/* ── Inputs / sliders ────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input {{
    background: rgba(0,229,255,.04) !important;
    border: 1px solid rgba(0,229,255,.22) !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
}}

/* ── Expander ────────────────────────────────────────────────── */
details {{
    background: rgba(0,229,255,.03) !important;
    border: 1px solid rgba(0,229,255,.10) !important;
    border-radius: 12px !important;
}}

/* ── Divider / HR ────────────────────────────────────────────── */
hr {{ border-color: rgba(0,229,255,.12) !important; }}

/* ── Caption ─────────────────────────────────────────────────── */
.stCaption {{ color: #475569 !important; }}

/* ── Scrollbar ───────────────────────────────────────────────── */
::-webkit-scrollbar {{ width:6px; height:6px; }}
::-webkit-scrollbar-track {{ background: #0a0f1e; }}
::-webkit-scrollbar-thumb {{ background: rgba(0,229,255,.3); border-radius:3px; }}
::-webkit-scrollbar-thumb:hover {{ background: rgba(0,229,255,.55); }}
</style>

<!-- starfield divs -->
<div id="st-s"></div>
<div id="st-m"></div>
<div id="st-l"></div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def detect_country(ticker: str) -> str:
    for sfx, country in {
        ".L":"UK", ".IL":"UK", ".PA":"France",
        ".DE":"Germany", ".F":"Germany", ".MU":"Germany",
        ".MI":"Italy", ".SW":"Switzerland",
        ".AS":"Netherlands", ".SI":"Singapore",
    }.items():
        if ticker.endswith(sfx):
            return country
    return "Other"


def build_chart_html(ticker: str) -> str:
    cfg = {"ticker": ticker, "apiBase": CHART_API_BASE, "defaultPeriod": "1y"}
    return (
        CHART_HTML_TEMPLATE
        .replace("__CHART_CONFIG__", json.dumps(cfg))
        .replace("__CHART_JS__", CHART_JS)
    )


def render_chart_view(ticker: str):
    st.caption(f"Grafico interattivo a candele — `{ticker}`")
    components.html(build_chart_html(ticker), height=760, scrolling=False)
    if st.button("Chiudi grafico", key=f"close_{ticker}", use_container_width=True):
        st.session_state.selected_chart_ticker = None
        st.rerun()


def _plotly_dark(fig, height=420):
    """Apply dark space theme to a Plotly figure."""
    fig.update_layout(
        paper_bgcolor="#060c1a",
        plot_bgcolor="#060c1a",
        font=dict(color="#a5d8ff", size=11),
        xaxis=dict(gridcolor="#1a2d4a", showline=False, zeroline=False),
        yaxis=dict(gridcolor="#1a2d4a", showline=False, zeroline=False),
        margin=dict(l=50, r=20, t=50, b=50),
        height=height,
    )
    return fig


def run_full_pipeline(prices, benchmark, name_lookup, isin_lookup, pb, st_txt):
    """
    Full analytics pipeline.
    Returns metrics, corr_display, correlation_xl, max_sharpe, min_vol,
            weekly_seasonality, returns
    """
    # --- Performance metrics --------------------------------------------------
    st_txt.text("⏳ Fase 3/4 — Calcolo metriche di performance (1Y/3Y/5Y, CAGR)...")
    pb.progress(52)
    metrics_perf, returns = _full_metrics(prices, benchmark)
    pb.progress(60)

    # --- Risk metrics ---------------------------------------------------------
    st_txt.text("⏳ Fase 3/4 — Calcolo rischio: Volatilità, Sharpe, Beta, Drawdown...")
    pb.progress(63)
    risk_df = pd.DataFrame({
        "Volatility 1Y":    compute_volatility(returns),
        "Sharpe Ratio":     compute_sharpe(returns),
        "Beta vs Benchmark":compute_beta(returns, benchmark),
        "Max Drawdown":     compute_max_drawdown(returns),
    })
    metrics = metrics_perf.join(risk_df)
    pb.progress(68)

    # --- Remove benchmark row -------------------------------------------------
    if benchmark in metrics.index:
        metrics = metrics.drop(index=benchmark)

    # --- Enrich with Country / Name / ISIN ------------------------------------
    metrics["Country"] = metrics.index.map(detect_country)
    metrics["Name"]    = metrics.index.map(lambda t: name_lookup.get(t, t))
    metrics["ISIN"]    = metrics.index.map(lambda t: isin_lookup.get(t, ""))
    front = ["Name", "ISIN", "Country"]
    metrics = metrics[front + [c for c in metrics.columns if c not in front]]
    pb.progress(70)

    # --- Correlation (tickers, for display) -----------------------------------
    corr_display = returns.drop(columns=[benchmark], errors="ignore").corr()

    # --- Optimization ---------------------------------------------------------
    st_txt.text("⏳ Fase 3/4 — Ottimizzazione portafoglio (Monte Carlo 4 000 simulazioni)...")
    pb.progress(72)
    try:
        max_sharpe_d, min_vol_d = optimize_portfolios(returns)
        max_sharpe = pd.Series(max_sharpe_d)
        min_vol    = pd.Series(min_vol_d)
    except Exception:
        max_sharpe = pd.Series(dtype=float)
        min_vol    = pd.Series(dtype=float)
    pb.progress(80)

    # --- Rename for Excel (ticker → ETF name) ---------------------------------
    name_map = metrics["Name"].to_dict()
    correlation_xl = returns.corr().copy()
    correlation_xl.index   = correlation_xl.index.map(lambda x: name_map.get(x, x))
    correlation_xl.columns = correlation_xl.columns.map(lambda x: name_map.get(x, x))
    max_sharpe.index = max_sharpe.index.map(lambda x: name_map.get(x, x))
    min_vol.index    = min_vol.index.map(lambda x: name_map.get(x, x))

    # --- Seasonality ----------------------------------------------------------
    st_txt.text("⏳ Fase 3/4 — Analisi stagionalità settimanale multi-orizzonte...")
    pb.progress(82)
    weekly_seasonality = compute_weekly_seasonality_multi(returns)
    pb.progress(85)

    return metrics, corr_display, correlation_xl, max_sharpe, min_vol, weekly_seasonality, returns


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

st.title("📊 ETF Portfolio Analyzer")

with st.sidebar:
    st.header("⬆️ Carica Portafoglio")
    uploaded_file = st.file_uploader(
        "File Excel (.xlsx / .xls)",
        type=["xlsx", "xls"],
        help="Il file deve contenere almeno una colonna 'Ticker'"
    )
    st.divider()
    st.header("⚙️ Impostazioni")
    years     = st.slider("Anni di storico", 1, 10, 5)
    benchmark = st.text_input("Benchmark", "IWDA.AS")

    # Persistent download button
    if st.session_state.download_report_bytes and st.session_state.download_report_name:
        st.divider()
        st.success("Report pronto!")
        st.download_button(
            label="📥 Scarica Report Excel",
            data=st.session_state.download_report_bytes,
            file_name=st.session_state.download_report_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="sidebar_dl",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# URL ?ticker= → open chart directly from Excel hyperlink
# ═══════════════════════════════════════════════════════════════════════════════

_params = st.query_params
if "ticker" in _params and not st.session_state.selected_chart_ticker:
    st.session_state.selected_chart_ticker = _params["ticker"]


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

if uploaded_file:
    try:
        # ── 0. Read Excel ─────────────────────────────────────────────────────
        with st.spinner("Lettura file Excel..."):
            df = pd.read_excel(uploaded_file)

        st.success(f"File caricato: **{df.shape[0]}** righe · **{df.shape[1]}** colonne")
        with st.expander("Anteprima file", expanded=False):
            st.dataframe(df.head(10), use_container_width=True)

        # ── Find columns ──────────────────────────────────────────────────────
        def _col(df, hints):
            for h in hints:
                for c in df.columns:
                    if h.lower() in str(c).lower():
                        return c
            return None

        ticker_col = _col(df, ["ticker", "symbol", "codice", "code"])
        name_col   = _col(df, ["name", "nome", "description", "etf"])
        isin_col   = _col(df, ["isin"])

        if not ticker_col:
            st.error("Nessuna colonna 'Ticker' trovata nel file Excel.")
            st.stop()

        tickers = (
            df[ticker_col].dropna()
            .astype(str).str.strip()
            .loc[lambda s: s != ""]
            .unique().tolist()
        )

        name_lookup = (
            df.set_index(ticker_col)[name_col].dropna().to_dict()
            if name_col else {}
        )
        isin_lookup = (
            df.set_index(ticker_col)[isin_col].dropna().to_dict()
            if isin_col else {}
        )

        st.info(f"Trovati **{len(tickers)}** ticker da analizzare")

        if benchmark not in tickers:
            tickers.append(benchmark)

        # ── PROGRESS BAR ──────────────────────────────────────────────────────
        pb  = st.progress(0)
        stx = st.empty()

        # ── FASE 1/4 — Download ───────────────────────────────────────────────
        stx.text("⏳ Fase 1/4 — Scaricamento dati di mercato da Yahoo Finance...")
        pb.progress(5)
        prices = fetch_prices(tickers, period=f"{years}y")
        pb.progress(25)

        # ── FASE 2/4 — Validation ─────────────────────────────────────────────
        stx.text("⏳ Fase 2/4 — Validazione qualità dati...")
        pb.progress(30)
        qr = validate_data_quality(prices)

        valid_assets = qr.get("valid_assets", list(prices.columns))
        if benchmark in prices.columns and benchmark not in valid_assets:
            valid_assets.append(benchmark)

        c1, c2, c3 = st.columns(3)
        c1.metric("Ticker Richiesti", len(tickers))
        c2.metric("Dati Validi",      qr.get("valid_count", len(valid_assets)))
        c3.metric("Problemi",         len(qr.get("issues", [])))

        if qr.get("issues"):
            with st.expander(f"⚠️ {len(qr['issues'])} problemi di qualità dati"):
                for iss in qr["issues"][:20]:
                    st.write(f"- {iss}")

        prices = prices[[c for c in prices.columns if c in valid_assets]]
        pb.progress(50)

        # ── FASE 3/4 — Full pipeline ──────────────────────────────────────────
        metrics, corr_display, correlation_xl, max_sharpe, min_vol, weekly_seas, returns = \
            run_full_pipeline(prices, benchmark, name_lookup, isin_lookup, pb, stx)

        # ── FASE 3/4 — Visualizations ─────────────────────────────────────────
        stx.text("⏳ Fase 3/4 — Generazione visualizzazioni...")
        pb.progress(86)

        st.subheader("📈 Performance del Portafoglio")

        tab_m, tab_c, tab_corr, tab_q = st.tabs([
            "📊 Metriche", "📉 Grafici", "🔗 Correlazione", "🔍 Qualità Dati"
        ])

        # ── Metrics table ──────────────────────────────────────────────────────
        with tab_m:
            pct_cols   = {"Perf 1Y","Perf 3Y","Perf 5Y","CAGR 3Y","CAGR 5Y",
                          "Annual Return","Avg Daily Return","Volatility 1Y","Max Drawdown"}
            ratio_cols = {"Sharpe Ratio","Beta vs Benchmark","Skewness","Kurtosis",
                          "Correlation vs Benchmark","Covariance vs Benchmark"}
            fmt = {}
            for c in metrics.columns:
                if c in pct_cols:    fmt[c] = "{:.2%}"
                elif c in ratio_cols: fmt[c] = "{:.2f}"
                elif c == "Current Price": fmt[c] = "{:.2f}"

            st.dataframe(
                metrics.style.format(fmt, na_rep="—"),
                use_container_width=True
            )

            st.markdown("---")
            st.markdown("**🕯️ Clicca su un ticker per aprire il grafico a candele**")
            display_tickers = [t for t in prices.columns if t != benchmark]
            cols4 = st.columns(5)
            for i, t in enumerate(display_tickers):
                with cols4[i % 5]:
                    if st.button(t, key=f"btn_{t}", use_container_width=True):
                        st.session_state.selected_chart_ticker = t
                        st.rerun()

        # ── Charts ──────────────────────────────────────────────────────────────
        with tab_c:
            col1, col2 = st.columns(2)

            with col1:
                fig_v = go.Figure(go.Bar(
                    x=metrics.index,
                    y=metrics.get("Volatility 1Y"),
                    marker_color="#00e5ff",
                    marker_line_width=0,
                    hovertemplate="%{x}: %{y:.2%}<extra></extra>",
                ))
                _plotly_dark(fig_v.update_layout(title="Volatilità Annualizzata",
                    yaxis_tickformat=".0%"))
                st.plotly_chart(fig_v, use_container_width=True)

            with col2:
                sr = metrics.get("Sharpe Ratio", pd.Series(dtype=float))
                fig_sr = go.Figure(go.Bar(
                    x=metrics.index,
                    y=sr,
                    marker_color=["#22c55e" if (v == v and v > 0) else "#ef4444" for v in sr],
                    marker_line_width=0,
                    hovertemplate="%{x}: %{y:.2f}<extra></extra>",
                ))
                _plotly_dark(fig_sr.update_layout(title="Sharpe Ratio"))
                st.plotly_chart(fig_sr, use_container_width=True)

            # Performance 1Y horizontal bar
            p1y = metrics.get("Perf 1Y", pd.Series(dtype=float)).dropna().sort_values()
            fig_p = go.Figure(go.Bar(
                x=p1y.values, y=p1y.index, orientation="h",
                marker_color=["#22c55e" if v > 0 else "#ef4444" for v in p1y],
                marker_line_width=0,
                hovertemplate="%{y}: %{x:.2%}<extra></extra>",
            ))
            _plotly_dark(fig_p.update_layout(
                title="Performance 1 Anno",
                xaxis_tickformat=".0%",
                height=max(380, len(p1y) * 22)
            ))
            st.plotly_chart(fig_p, use_container_width=True)

            # Max Drawdown
            dd = metrics.get("Max Drawdown", pd.Series(dtype=float)).dropna().sort_values()
            fig_dd = go.Figure(go.Bar(
                x=dd.index, y=dd.values,
                marker_color="#ef4444",
                marker_line_width=0,
                hovertemplate="%{x}: %{y:.2%}<extra></extra>",
            ))
            _plotly_dark(fig_dd.update_layout(
                title="Max Drawdown",
                yaxis_tickformat=".0%"
            ))
            st.plotly_chart(fig_dd, use_container_width=True)

        # ── Correlation heatmap ─────────────────────────────────────────────────
        with tab_corr:
            if not corr_display.empty:
                fig_corr = go.Figure(go.Heatmap(
                    z=corr_display.values,
                    x=list(corr_display.columns),
                    y=list(corr_display.index),
                    colorscale=[
                        [0.0, "#ef4444"],
                        [0.5, "#1a2d4a"],
                        [1.0, "#22c55e"],
                    ],
                    zmin=-1, zmax=1,
                    text=corr_display.values.round(2),
                    texttemplate="%{text}",
                    colorbar=dict(
                        tickfont=dict(color="#a5d8ff"),
                        title=dict(text="Corr", font=dict(color="#a5d8ff"))
                    ),
                    hovertemplate="x: %{x}<br>y: %{y}<br>corr: %{z:.2f}<extra></extra>",
                ))
                _plotly_dark(fig_corr.update_layout(
                    title="Matrice di Correlazione (Ticker)",
                    height=max(450, len(corr_display) * 28)
                ))
                st.plotly_chart(fig_corr, use_container_width=True)
            else:
                st.warning("Dati insufficienti per la matrice di correlazione.")

        # ── Data quality ────────────────────────────────────────────────────────
        with tab_q:
            completeness = prices.notna().sum() / len(prices) * 100
            fig_comp = go.Figure(go.Bar(
                x=completeness.index,
                y=completeness.values,
                marker_color="#8b5cf6",
                marker_line_width=0,
                hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
            ))
            _plotly_dark(fig_comp.update_layout(
                title="Completezza Dati per Asset (%)",
                yaxis=dict(range=[0, 105], gridcolor="#1a2d4a"),
            ))
            st.plotly_chart(fig_comp, use_container_width=True)

            if qr.get("warnings"):
                with st.expander(f"⚡ {len(qr['warnings'])} avvisi"):
                    for w in qr["warnings"][:20]:
                        st.write(f"- {w}")

        pb.progress(88)

        # ── FASE 4/4 — Excel export ───────────────────────────────────────────
        stx.text("⏳ Fase 4/4 — Generazione report Excel multi-foglio (con hyperlink ai grafici)...")
        pb.progress(90)

        ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = OUTPUT_DIR / f"portfolio_analysis_{ts}.xlsx"
        export_to_excel(metrics, correlation_xl, max_sharpe, min_vol, weekly_seas, output_file)
        report_bytes = output_file.read_bytes()

        pb.progress(100)
        stx.text("✅ Analisi completata! Report Excel pronto per il download.")

        st.session_state.download_report_path  = str(output_file)
        st.session_state.download_report_name  = output_file.name
        st.session_state.download_report_bytes = report_bytes

        # ── DOWNLOAD BUTTON (prominente) ──────────────────────────────────────
        st.success("✅ Analisi completata!")
        st.markdown("---")
        _, col_dl, _ = st.columns([1, 2, 1])
        with col_dl:
            st.download_button(
                label="📥  Scarica Report Excel Completo",
                data=report_bytes,
                file_name=output_file.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="main_dl",
            )
        st.markdown(
            "<p style='text-align:center;color:#475569;font-size:.85rem;'>"
            "Il report include: Dashboard · Metriche · Correlazione · "
            "Max Sharpe · Min Vol · Stagionalità Settimanale · "
            "Hyperlink ai grafici a candele per ogni ETF"
            "</p>",
            unsafe_allow_html=True,
        )

    except Exception as exc:
        st.session_state.download_report_path  = None
        st.session_state.download_report_name  = None
        st.session_state.download_report_bytes = None
        st.error(f"Errore: {exc}")
        import traceback
        st.code(traceback.format_exc())

else:
    # ── Landing page ───────────────────────────────────────────────────────────
    st.markdown("""
<p style='color:#64748b; font-size:1.05rem; margin-bottom:24px;'>
Carica il file Excel del tuo portafoglio dalla barra laterale per avviare l'analisi completa.
</p>
""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📋 Formato Atteso")
        st.dataframe(pd.DataFrame({
            "Ticker": ["IWDA.AS", "VWCE.DE", "XDWD.L"],
            "ISIN":   ["IE00B4L5Y983", "IE00BK5BQT80", "IE00BK1PV551"],
            "Name":   ["iShares MSCI World", "Vanguard FTSE All-World", "iShares MSCI World"],
        }), use_container_width=True)
    with c2:
        st.subheader("✨ Funzionalità")
        st.markdown("""
- 📡 **Download** dati da Yahoo Finance (fallback Stooq)
- 🔍 **Validazione qualità** su tutti gli asset
- 📊 **Metriche complete**: CAGR 1/3/5Y, Sharpe, Beta, Max Drawdown
- 🧮 **Ottimizzazione**: Max Sharpe & Min Vol (4 000 simulazioni Monte Carlo)
- 🔗 **Correlazione** interattiva heatmap
- 🗓️ **Stagionalità settimanale** multi-orizzonte (2/3/4/5 anni)
- 📥 **Report Excel** 6 fogli con hyperlink ai grafici a candele
- 🕯️ **Grafici a candele** interattivi con SMA/EMA/Volume
""")


# ═══════════════════════════════════════════════════════════════════════════════
# CHART DIALOG
# ═══════════════════════════════════════════════════════════════════════════════

if st.session_state.selected_chart_ticker:
    _t = st.session_state.selected_chart_ticker
    if hasattr(st, "dialog"):
        @st.dialog(f"📈 {_t}", width="large")
        def _dlg():
            render_chart_view(_t)
        _dlg()
    else:
        st.subheader(f"📈 {_t}")
        render_chart_view(_t)


st.caption("ETF Portfolio Analyzer · Streamlit · Yahoo Finance · openpyxl")
