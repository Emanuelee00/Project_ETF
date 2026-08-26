"""FastAPI backend for ETF Portfolio Analyzer."""

from __future__ import annotations

import asyncio
import io
import json
import re
import sys
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import uvicorn
import yfinance as yf
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ── path setup ───────────────────────────────────────────────────────────────
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from analytics import fetch_prices, compute_metrics as _full_metrics, validate_data_quality
from risk_metrics import compute_volatility, compute_sharpe, compute_beta, compute_max_drawdown
from optimization import optimize_portfolios
from seasonality import compute_weekly_seasonality_multi
from excel_export import export_to_excel
from chart_backend import get_chart_payload
from country import detect_country
from data_cache import cache_stats, background_download_all

# ── paths ─────────────────────────────────────────────────────────────────────
BASE_DIR      = SRC_DIR.parent
DATA_DIR      = BASE_DIR / "data"
OUTPUT_DIR    = BASE_DIR / "output"
STATIC_DIR    = SRC_DIR  / "static"
MAPPING_FILE  = DATA_DIR / "isin_ticker_mapping.csv"
ORIGINAL_FILE = DATA_DIR / "himalaya.csv"
OUTPUT_DIR.mkdir(exist_ok=True)

BENCHMARK = "IWDA.AS"

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="ETF Portfolio Analyzer", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# job_id → {queue, output_path, output_name, summary, error}
JOBS: dict[str, dict[str, Any]] = {}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def normalize_value(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def looks_like_isin(value: str) -> bool:
    value = normalize_value(value).upper()
    return bool(re.fullmatch(r"[A-Z]{2}[A-Z0-9]{10}", value))


def looks_like_ticker(value: str) -> bool:
    value = normalize_value(value).upper()
    if not value or len(value) > 20:
        return False
    if looks_like_isin(value):
        return False
    if value.replace('.', '', 1).replace('-', '', 1).isdigit():
        return False
    if not re.search(r"[A-Z]", value):
        return False
    return bool(re.fullmatch(r"[A-Z0-9\.-]+", value))


def _find_header_column(df: pd.DataFrame, headers: list[str], keywords: tuple[str, ...]) -> str | None:
    """Return the first column whose lowercased header contains one of the keywords."""
    for keyword in keywords:
        for idx, header in enumerate(headers):
            if keyword in header:
                return df.columns[idx]
    return None


def _build_mapping_lookup_sets(mapping_df: pd.DataFrame | None) -> tuple[set, set]:
    """Build normalized ISIN/ticker lookup sets from the mapping file, if provided."""
    if mapping_df is None:
        return set(), set()
    mapping_isins = set(
        mapping_df["ISIN"]
        .astype(str)
        .map(normalize_value)
        .str.replace(r"[^A-Z0-9]", "", regex=True)
        .str.upper()
        .tolist()
    )
    mapping_tickers = set(
        mapping_df["Ticker"]
        .astype(str)
        .map(normalize_value)
        .str.upper()
        .tolist()
    )
    return mapping_isins, mapping_tickers


def _best_isin_and_ticker_columns(
    df: pd.DataFrame, mapping_isins: set, mapping_tickers: set
) -> tuple[tuple[str, float] | None, tuple[str, float] | None]:
    """Score each column for how ISIN-like or ticker-like its values are; return the best of each."""
    best_isin = None
    best_isin_score = -1.0
    best_ticker = None
    best_ticker_score = -1.0

    for col in df.columns:
        values = df[col].astype(str).map(normalize_value)
        values = values[values != ""]
        if values.empty:
            continue

        total = len(values)
        isin_count = int(values.map(looks_like_isin).sum())
        ticker_count = int(values.map(looks_like_ticker).sum())
        mapped_isin_count = int(values.str.upper().str.replace(r"[^A-Z0-9]", "", regex=True).isin(mapping_isins).sum()) if mapping_isins else 0
        mapped_ticker_count = int(values.str.upper().isin(mapping_tickers).sum()) if mapping_tickers else 0
        numeric_count = int(values.apply(lambda v: v.replace('.', '', 1).replace('-', '', 1)).str.isdigit().sum())

        isin_score = (mapped_isin_count * 4 + isin_count * 2)
        ticker_score = (mapped_ticker_count * 4 + ticker_count * 1)

        # Penalize numeric-heavy columns if no mapping found
        if numeric_count / total > 0.8 and mapped_isin_count + mapped_ticker_count == 0:
            isin_score *= 0.1
            ticker_score *= 0.1

        if isin_score > best_isin_score:
            best_isin_score = isin_score
            best_isin = (col, isin_score)

        if ticker_score > best_ticker_score:
            best_ticker_score = ticker_score
            best_ticker = (col, ticker_score)

    return best_isin, best_ticker


def select_input_column(df: pd.DataFrame, mapping_df: pd.DataFrame | None = None) -> tuple[str | None, str]:
    """Select the column containing ISIN or ticker from the uploaded DataFrame.

    Strategy:
    1. Look for explicit "isin" in headers → return as ISIN
    2. If not found, analyze data with heuristics, preferring ISIN over ticker
    3. Only if no ISIN found, look for "ticker" in headers
    """
    headers = [str(c).lower() for c in df.columns]

    isin_header_col = _find_header_column(df, headers, ("isin", "is in"))
    if isin_header_col is not None:
        return isin_header_col, "isin"

    mapping_isins, mapping_tickers = _build_mapping_lookup_sets(mapping_df)
    best_isin, best_ticker = _best_isin_and_ticker_columns(df, mapping_isins, mapping_tickers)

    if best_isin is not None and best_isin[1] > 0:
        return best_isin[0], "isin"

    if best_ticker is not None and best_ticker[1] > 0:
        return best_ticker[0], "ticker"

    ticker_header_col = _find_header_column(df, headers, ("ticker", "symbol", "asset"))
    if ticker_header_col is not None:
        return ticker_header_col, "ticker"

    return None, "unknown"


def _emit(job_id: str, loop, **kwargs):
    """Thread-safe SSE event push."""
    JOBS[job_id]["queue"].put_nowait if loop is None else None
    event = kwargs
    loop.call_soon_threadsafe(JOBS[job_id]["queue"].put_nowait, event)


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE (runs in background thread)
# ─────────────────────────────────────────────────────────────────────────────

def _load_and_prepare_mapping() -> pd.DataFrame:
    if not MAPPING_FILE.exists():
        raise FileNotFoundError(f"Mapping file non trovato: {MAPPING_FILE}")

    mapping_df = pd.read_csv(MAPPING_FILE)
    mapping_df.columns = mapping_df.columns.str.strip()
    mapping_df["ISIN"] = (
        mapping_df["ISIN"]
        .astype(str)
        .map(normalize_value)
        .str.replace(r"[^A-Z0-9]", "", regex=True)
        .str.upper()
    )
    mapping_df["Ticker"] = (
        mapping_df["Ticker"]
        .astype(str)
        .map(normalize_value)
        .str.upper()
    )
    return mapping_df.loc[mapping_df["ISIN"] != ""].copy()


def _resolve_isins_via_yfinance(isins: list[str]) -> list[str]:
    """Confirm which ISINs are directly tradeable tickers via yfinance."""
    resolved = []
    for isin in isins:
        try:
            fi = yf.Ticker(isin).fast_info
            price = getattr(fi, 'last_price', None) or getattr(fi, 'regularMarketPrice', None)
            if price and float(price) > 0:
                resolved.append(isin)
        except Exception:
            pass
    return resolved


def _extract_tickers_from_isins(raw_values: list[str], mapping_df: pd.DataFrame, emit) -> tuple[list[str], list[str]]:
    """Resolve uploaded ISIN values to tickers via the mapping file, falling back to yfinance."""
    isins_uploaded = [val.upper() for val in raw_values if looks_like_isin(val)]
    if not isins_uploaded:
        raise ValueError(
            "Non sono stati trovati ISIN validi nel file caricato. "
            "Verifica il formato della colonna selezionata."
        )
    emit(1, f"ISIN trovati nel file: {len(isins_uploaded)}")

    mapped_df = mapping_df[mapping_df["ISIN"].isin(isins_uploaded)]
    has_ticker = mapped_df["Ticker"].notna() & (mapped_df["Ticker"].str.strip() != "")

    # Mantieni TUTTI gli ISIN, anche quelli senza ticker
    tickers = mapped_df.loc[has_ticker, "Ticker"].astype(str).str.strip().unique().tolist()

    isins_without_ticker = mapped_df.loc[~has_ticker, "ISIN"].tolist()
    unmapped_isins = [isin for isin in isins_uploaded if isin not in mapped_df["ISIN"].tolist()]

    if unmapped_isins:
        emit(1, f"ISIN non trovati nel mapping: {len(unmapped_isins)}")
        if len(unmapped_isins) <= 10:
            emit(1, f"ISIN non mappati: {', '.join(unmapped_isins)}")

    if isins_without_ticker:
        emit(1, f"ISIN senza ticker nel mapping: {len(isins_without_ticker)} (includesi nel report senza dati di prezzo)")

    if not tickers:
        emit(2, "Nessun ticker trovato; il report conterrà solo gli asset senza dati di prezzo.")

    # ── Risoluzione ISINs non mappati via yfinance ───────────────
    extra_to_try = list(set(unmapped_isins) | set(isins_without_ticker))
    if extra_to_try:
        emit(1, f"Tentativo risoluzione {len(extra_to_try)} ISIN non mappati via yfinance…")
        resolved_extra = _resolve_isins_via_yfinance(extra_to_try)
        if resolved_extra:
            tickers.extend(resolved_extra)
            emit(1, f"ISIN risolti direttamente via yfinance: {len(resolved_extra)}")

    return tickers, isins_uploaded


def _extract_tickers(df_upload: pd.DataFrame, mapping_df: pd.DataFrame, emit) -> tuple[list[str], str, list[str]]:
    """Identify the ISIN/ticker column and resolve it to a deduplicated ticker list."""
    selected_col, detected_kind = select_input_column(df_upload, mapping_df)
    if not selected_col:
        raise ValueError("Impossibile identificare la colonna contenente ISIN o ticker nel file caricato.")

    raw_values = (
        df_upload[selected_col]
        .astype(str)
        .map(normalize_value)
        .loc[lambda s: s != ""]
        .unique()
        .tolist()
    )
    emit(1, f"Valori trovati nella colonna '{selected_col}': {len(raw_values)}")

    isins_uploaded: list[str] = []
    if detected_kind == "ticker":
        tickers = [val for val in raw_values if looks_like_ticker(val)]
        if not tickers:
            raise ValueError(
                "Non sono stati trovati ticker validi nella colonna selezionata. "
                "Verifica il formato del file caricato."
            )
        emit(1, f"Ticker rilevati direttamente dal file: {len(tickers)}")
    else:
        tickers, isins_uploaded = _extract_tickers_from_isins(raw_values, mapping_df, emit)

    tickers = [t for t in tickers if t and str(t).strip() != ""]
    # Deduplicazione preservando ordine
    seen: set = set()
    tickers = [t for t in tickers if not (t in seen or seen.add(t))]
    if BENCHMARK not in tickers:
        tickers.append(BENCHMARK)

    emit(1, f"Ticker trovati: {len(tickers)}")
    return tickers, detected_kind, isins_uploaded


def _download_and_validate_prices(tickers: list[str], emit) -> pd.DataFrame:
    emit(2, "Scaricamento dati di mercato da Yahoo Finance…")
    prices = fetch_prices(tickers)
    if prices.empty:
        raise ValueError("Nessun dato scaricato da Yahoo Finance.")

    missing_tickers = [t for t in tickers if t not in prices.columns]
    if missing_tickers:
        for ticker in missing_tickers:
            prices[ticker] = pd.NA
        prices = prices[tickers]
    emit(3, f"Prezzi scaricati: {prices.shape[1]} asset  "
            f"({prices.index.min().date()} → {prices.index.max().date()})")
    if missing_tickers:
        emit(3, f"Dati mancanti per {len(missing_tickers)} asset; saranno comunque inclusi nel report.")

    emit(3, "Validazione qualità dati…")
    qr = validate_data_quality(prices)
    valid_assets = qr.get("valid_assets", list(prices.columns))
    if BENCHMARK in prices.columns and BENCHMARK not in valid_assets:
        valid_assets.append(BENCHMARK)
    emit(4, f"Asset validi: {len(valid_assets)} / {len(tickers)}")
    invalid_count = len(tickers) - len(valid_assets)
    if invalid_count > 0:
        emit(4, f"{invalid_count} asset con dati incompleti o anomalie saranno comunque inclusi nel report.")

    return prices


def _resolve_display_name(ticker: str, name_from_lookup: str) -> str:
    """Return real name; if it looks like an ISIN or is empty, try yfinance."""
    candidate = str(name_from_lookup).strip() if name_from_lookup else ""
    if candidate and not looks_like_isin(candidate):
        return candidate
    try:
        info = yf.Ticker(ticker).fast_info
        real_name = getattr(info, 'long_name', None) or getattr(info, 'short_name', None) or ""
        if not real_name:
            full_info = yf.Ticker(ticker).info
            real_name = full_info.get("longName") or full_info.get("shortName") or ""
        if real_name and not looks_like_isin(real_name):
            return real_name
    except Exception:
        pass
    return ticker  # last resort: ticker symbol, not ISIN


def _compute_metrics_with_enrichment(prices: pd.DataFrame, mapping_df: pd.DataFrame, emit) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute performance + risk metrics, then enrich with Name/ISIN/Country."""
    emit(4, "Calcolo metriche di performance e rischio…")
    metrics_perf, returns = _full_metrics(prices, BENCHMARK)

    risk_df = pd.DataFrame({
        "Volatility 1Y":     compute_volatility(returns),
        "Sharpe Ratio":      compute_sharpe(returns),
        "Beta vs Benchmark": compute_beta(returns, BENCHMARK),
        "Max Drawdown":      compute_max_drawdown(returns),
    })
    metrics = metrics_perf.join(risk_df)

    if BENCHMARK in metrics.index:
        metrics = metrics.drop(index=BENCHMARK)

    original_df = pd.read_csv(ORIGINAL_FILE) if ORIGINAL_FILE.exists() else pd.DataFrame()
    name_lookup: dict = {}
    isin_lookup: dict = (
        mapping_df[["Ticker", "ISIN"]]
        .drop_duplicates("Ticker")
        .set_index("Ticker")["ISIN"]
        .to_dict()
    )

    if not original_df.empty and "Code ISIN" in original_df.columns:
        nm_col = original_df.columns[0]
        nm_df  = original_df[["Code ISIN", nm_col]].dropna()
        nm_df.columns = ["ISIN", "Name"]
        merged = mapping_df.merge(nm_df, on="ISIN", how="left")
        name_lookup = (
            merged[["Ticker", "Name"]]
            .drop_duplicates("Ticker")
            .set_index("Ticker")["Name"]
            .dropna().to_dict()
        )

    metrics["ISIN"] = metrics.index.map(lambda t: isin_lookup.get(t, ""))
    metrics["Country"] = metrics.apply(
        lambda row: detect_country(row.name, row["ISIN"]), axis=1
    )
    metrics["Name"] = metrics.index.map(
        lambda t: _resolve_display_name(t, name_lookup.get(t, ""))
    )
    front   = ["Name", "ISIN", "Country"]
    metrics = metrics[front + [c for c in metrics.columns if c not in front]]
    emit(5, f"Metriche calcolate per {len(metrics)} ETF")

    return metrics, returns


def _optimize_and_correlate(returns: pd.DataFrame, metrics: pd.DataFrame, emit) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    emit(6, "Ottimizzazione portafoglio (Monte Carlo 4 000 simulazioni)…")
    corr_xl = returns.corr()
    try:
        ms_d, mv_d = optimize_portfolios(returns)
        max_sharpe = pd.Series(ms_d)
        min_vol    = pd.Series(mv_d)
    except Exception:
        max_sharpe = pd.Series(dtype=float)
        min_vol    = pd.Series(dtype=float)

    name_map = metrics["Name"].to_dict()
    for df_ in (corr_xl, max_sharpe, min_vol):
        if hasattr(df_, "index"):
            df_.index = df_.index.map(lambda x: name_map.get(x, x))
        if hasattr(df_, "columns"):
            df_.columns = df_.columns.map(lambda x: name_map.get(x, x))

    return corr_xl, max_sharpe, min_vol


# All available metric columns — send everything computed to the frontend
_SUMMARY_COLS = [
    "Name", "ISIN", "Country", "Current Price",
    "Perf 1Y", "Perf 3Y", "Perf 5Y",
    "CAGR 3Y", "CAGR 5Y",
    "Avg Daily Return", "Annual Return",
    "Skewness", "Kurtosis",
    "Correlation vs Benchmark", "Covariance vs Benchmark",
    "Volatility 1Y", "Sharpe Ratio", "Beta vs Benchmark", "Max Drawdown",
]


def _build_job_summary(metrics: pd.DataFrame, isins_uploaded: list[str], detected_kind: str, tickers: list[str]) -> dict:
    send_cols = [c for c in _SUMMARY_COLS if c in metrics.columns]
    return {
        "total_assets_analyzed": len(metrics),
        "total_assets_uploaded": len(isins_uploaded) if detected_kind == "isin" else len(tickers),
        "avg_sharpe":   round(float(metrics["Sharpe Ratio"].mean(skipna=True)), 2)
                        if "Sharpe Ratio" in metrics else 0,
        "avg_vol":      round(float(metrics["Volatility 1Y"].mean(skipna=True)), 4)
                        if "Volatility 1Y" in metrics else 0,
        "avg_drawdown": round(float(metrics["Max Drawdown"].mean(skipna=True)), 4)
                        if "Max Drawdown" in metrics else 0,
        "input_type": detected_kind,
        "tickers": [str(t) for t in metrics.index.tolist()],
        "metrics": json.loads(
            metrics[send_cols]
            .fillna("")
            .reset_index()
            .rename(columns={"index": "Ticker"})
            .to_json(orient="records", force_ascii=False)
        ),
    }


def run_pipeline(job_id: str, excel_bytes: bytes, loop):
    TOTAL = 8

    def emit(step: int, msg: str, done: bool = False, error: str | None = None):
        pct = int(100 * step / TOTAL)
        event = {"step": step, "total": TOTAL, "pct": pct, "msg": msg,
                 "done": done, "error": error}
        if done:
            event["output_name"] = JOBS[job_id].get("output_name")
            event["summary"]     = JOBS[job_id].get("summary")
        loop.call_soon_threadsafe(JOBS[job_id]["queue"].put_nowait, event)

    try:
        emit(0, "Lettura file Excel caricato…")
        df_upload = pd.read_excel(io.BytesIO(excel_bytes))

        mapping_df = _load_and_prepare_mapping()
        tickers, detected_kind, isins_uploaded = _extract_tickers(df_upload, mapping_df, emit)
        prices = _download_and_validate_prices(tickers, emit)
        metrics, returns = _compute_metrics_with_enrichment(prices, mapping_df, emit)
        corr_xl, max_sharpe, min_vol = _optimize_and_correlate(returns, metrics, emit)

        emit(7, "Analisi stagionalità settimanale multi-orizzonte…")
        weekly_seas = compute_weekly_seasonality_multi(returns)

        emit(7, "Generazione report Excel completo (6 fogli + hyperlink grafici)…")
        ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = OUTPUT_DIR / f"portfolio_analysis_{ts}.xlsx"
        export_to_excel(metrics, corr_xl, max_sharpe, min_vol, weekly_seas, output_file)

        JOBS[job_id]["output_name"] = output_file.name
        JOBS[job_id]["summary"] = _build_job_summary(metrics, isins_uploaded, detected_kind, tickers)

        emit(8, "Analisi completata!", done=True)

    except Exception as exc:
        import traceback
        emit(0, str(exc), done=True, error=traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_excel(file: UploadFile = File(...)):
    content = await file.read()
    job_id  = str(uuid.uuid4())
    loop    = asyncio.get_running_loop()
    JOBS[job_id] = {
        "queue":       asyncio.Queue(),
        "output_name": None,
        "summary":     None,
    }
    threading.Thread(
        target=run_pipeline, args=(job_id, content, loop), daemon=True
    ).start()
    return {"job_id": job_id}


@app.get("/api/progress/{job_id}")
async def progress_stream(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "Job not found")

    async def generate():
        q = JOBS[job_id]["queue"]
        try:
            while True:
                event = await asyncio.wait_for(q.get(), timeout=300)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("done"):
                    break
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'done': True, 'error': 'Timeout — pipeline troppo lunga.'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering":"no",
            "Connection":       "keep-alive",
        },
    )


@app.get("/api/download/{filename}")
async def download_file(filename: str):
    safe = OUTPUT_DIR / Path(filename).name
    if not safe.exists():
        raise HTTPException(404, "File non trovato")
    return FileResponse(
        str(safe),
        filename=safe.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/chart/{ticker}")
async def chart_endpoint(ticker: str, period: str = "1y", interval: str = "1d"):
    try:
        data = await asyncio.to_thread(get_chart_payload, ticker, period, interval)
        return data
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


def _global_search(q: str, limit: int = 12) -> list[dict]:
    """Search any ticker globally via yfinance Search + fuzzy fallback."""
    results = []
    try:
        raw = yf.Search(q, max_results=limit, news_count=0, enable_fuzzy_query=True).quotes or []
        for r in raw:
            results.append({
                "symbol":   r.get("symbol", ""),
                "name":     r.get("longname") or r.get("shortname") or "",
                "type":     r.get("quoteType", ""),
                "exchange": r.get("exchDisp", ""),
                "score":    r.get("score", 0),
            })
    except Exception:
        pass
    return results


@app.get("/api/global-search")
async def global_search_endpoint(q: str, limit: int = 12):
    if not q or len(q.strip()) < 1:
        return {"results": []}
    results = await asyncio.to_thread(_global_search, q.strip(), limit)
    return {"results": results}


def _get_news_payload(ticker: str) -> dict:
    """Fetch news from yfinance and compute keyword-based sentiment."""
    POSITIVE_WORDS = {
        "surge", "rally", "gain", "profit", "grow", "rise", "bull", "beat", "record",
        "upgrade", "strong", "positive", "boost", "expand", "soar", "climb", "hit",
        "top", "success", "dividend", "buy", "outperform", "exceeds", "upside",
        "revenue", "earnings", "acquisition", "partnership", "launch", "innovation",
    }
    NEGATIVE_WORDS = {
        "drop", "fall", "loss", "decline", "crash", "bear", "miss", "cut", "risk",
        "downgrade", "weak", "negative", "shrink", "plunge", "slump", "debt", "sell",
        "underperform", "warning", "lawsuit", "fine", "probe", "fraud", "default",
        "recession", "layoff", "restructure", "volatile", "concern", "disappoint",
    }

    raw_news = yf.Ticker(ticker).news or []
    articles = []
    total_score = 0

    for item in raw_news[:20]:
        # Support both old format (flat keys) and new format (nested 'content')
        if "content" in item and isinstance(item["content"], dict):
            c = item["content"]
            title = c.get("title", "")
            publisher = (c.get("provider") or {}).get("displayName", "")
            link = (c.get("canonicalUrl") or c.get("clickThroughUrl") or {}).get("url", "")
            pub_date = c.get("pubDate") or c.get("displayTime") or ""
            try:
                date_str = datetime.strptime(pub_date[:10], "%Y-%m-%d").strftime("%Y-%m-%d") if pub_date else "—"
            except Exception:
                date_str = "—"
        else:
            title = item.get("title", "")
            publisher = item.get("publisher", "")
            link = item.get("link", "")
            ts = item.get("providerPublishTime", 0)
            date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d") if ts else "—"

        words = set(title.lower().split())
        pos = len(words & POSITIVE_WORDS)
        neg = len(words & NEGATIVE_WORDS)
        if pos > neg:
            sentiment = "positive"
            score = min(pos * 15, 50)
        elif neg > pos:
            sentiment = "negative"
            score = max(-neg * 15, -50)
        else:
            sentiment = "neutral"
            score = 0
        total_score += score

        articles.append({
            "title": title,
            "publisher": publisher,
            "link": link,
            "date": date_str,
            "sentiment": sentiment,
            "score": score,
        })

    # Clamp overall score to [-100, 100]
    overall = max(-100, min(100, total_score))

    # Buy/Sell/Hold signal
    if overall >= 20:
        signal = "BUY"
    elif overall <= -20:
        signal = "SELL"
    else:
        signal = "HOLD"

    return {"ticker": ticker, "articles": articles, "overall_score": overall, "signal": signal}


@app.get("/api/news/{ticker}")
async def news_endpoint(ticker: str):
    try:
        data = await asyncio.to_thread(_get_news_payload, ticker)
        return data
    except Exception as exc:
        raise HTTPException(500, str(exc))


class StrategyRequest(BaseModel):
    ticker: str
    period: str = "1y"
    strategy: str = "ma_cross"     # "ma_cross" | "rsi"
    short_ma: int = 10
    long_ma: int = 50
    rsi_period: int = 14
    rsi_oversold: int = 30
    rsi_overbought: int = 70
    risk_per_trade: float = 0.02
    reward_ratio: float = 2.0
    spread: float = Field(default=0.0, ge=0.0)
    slippage: float = Field(default=0.0, ge=0.0)
    commission_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    use_rsi_filter: bool = True    # RSI overbought/oversold filter
    use_trend_filter: bool = True  # Trend-direction filter (200-day MA)


def _compute_rsi(series: "pd.Series", period: int = 14) -> "pd.Series":
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - 100 / (1 + rs)
    return rsi



# Calendar-day length of each selectable period, used to fetch extra history ahead of
# the displayed window so long lookback indicators (e.g. the 200-day trend filter) have
# room to warm up even when the user picks a short period like 3mo/6mo.
_PERIOD_CALENDAR_DAYS = {
    "3mo": 92, "6mo": 183, "1y": 365, "2y": 730, "5y": 1826, "10y": 3653,
}
_INDICATOR_WARMUP_CALENDAR_DAYS = 380  # covers a 200-trading-day MA plus margin


def _fetch_price_history(ticker: str, period: str) -> pd.DataFrame:
    display_days = _PERIOD_CALENDAR_DAYS.get(period, 365)
    end = datetime.now()
    start = end - timedelta(days=display_days + _INDICATOR_WARMUP_CALENDAR_DAYS)
    return yf.Ticker(ticker).history(start=start, end=end, interval="1d")


def _prepare_backtest_frame(hist: pd.DataFrame, req: StrategyRequest) -> pd.DataFrame:
    """Compute indicators + the raw MA-crossover signal on top of already-fetched price history,
    then trim to the user's selected display period now that indicators have warmed up."""
    need = max(req.long_ma, 200 if req.use_trend_filter else 0) + 20
    if hist.empty or len(hist) < need:
        raise ValueError(
            f"Insufficient data for backtest (need ≥{need} bars, got {len(hist)})"
        )

    df = hist[["Close", "High", "Low"]].copy()
    df["short_ma"]  = df["Close"].rolling(req.short_ma).mean()
    df["long_ma"]   = df["Close"].rolling(req.long_ma).mean()
    df["rsi"]       = _compute_rsi(df["Close"], 14)
    if req.use_trend_filter:
        df["trend_ma"] = df["Close"].rolling(200).mean()

    df["cross"] = 0
    df.loc[df.index[req.short_ma:], "cross"] = (
        df["short_ma"][req.short_ma:] > df["long_ma"][req.short_ma:]
    ).astype(int)

    display_days = _PERIOD_CALENDAR_DAYS.get(req.period, 365)
    cutoff = df.index.max() - pd.Timedelta(days=display_days)
    return df[df.index >= cutoff]


def _prepare_rsi_backtest_frame(hist: pd.DataFrame, req: StrategyRequest) -> pd.DataFrame:
    """RSI mean-reversion: go long while RSI is below the oversold level, flat once it
    crosses back above the overbought level (ported from strategy_projects/spy_rsi_project)."""
    need = req.rsi_period + 20
    if hist.empty or len(hist) < need:
        raise ValueError(
            f"Insufficient data for backtest (need ≥{need} bars, got {len(hist)})"
        )

    df = hist[["Close", "High", "Low"]].copy()
    df["rsi"] = _compute_rsi(df["Close"], req.rsi_period)

    signal = pd.Series(float("nan"), index=df.index)
    signal[df["rsi"] < req.rsi_oversold] = 1
    signal[df["rsi"] > req.rsi_overbought] = 0
    df["signal"] = signal.ffill().fillna(0)

    display_days = _PERIOD_CALENDAR_DAYS.get(req.period, 365)
    cutoff = df.index.max() - pd.Timedelta(days=display_days)
    return df[df.index >= cutoff]


def _simulate_rsi_trades(df: pd.DataFrame, req: StrategyRequest) -> tuple[float, list[float], list[dict], list[dict]]:
    """Walk the RSI signal column applying entry/exit rules; mirrors _simulate_trades'
    output shape so the same rendering/response code works for both strategies."""
    capital = 10_000.0
    equity: list[float] = [capital]
    trades: list[dict] = []
    signals: list[dict] = []
    in_trade = False
    entry_price = 0.0

    for i in range(1, len(df)):
        prev_sig = df["signal"].iloc[i - 1]
        curr_sig = df["signal"].iloc[i]
        price    = float(df["Close"].iloc[i])
        date_str = str(df.index[i].date())

        if not in_trade and curr_sig == 1 and prev_sig == 0:
            in_trade = True
            entry_price = price + req.spread + req.slippage
            signals.append({"date": date_str, "type": "buy", "price": round(entry_price, 4)})

        elif in_trade and curr_sig == 0 and prev_sig == 1:
            exit_price = max(price - req.spread - req.slippage, 0.0)
            pnl_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else 0
            position_value = capital * req.risk_per_trade
            commission = position_value * req.commission_rate * 2
            trade_pnl = position_value * pnl_pct - commission
            capital += trade_pnl
            is_win = trade_pnl > 0
            trades.append({
                "date":   date_str,
                "pnl":    round(trade_pnl, 2),
                "is_win": is_win,
                "entry":  round(entry_price, 4),
                "exit":   round(exit_price, 4),
                "costs":  round(commission, 2),
            })
            signals.append({"date": date_str, "type": "sell", "price": round(exit_price, 4)})
            in_trade = False

        equity.append(capital)

    return capital, equity, trades, signals


def _simulate_trades(df: pd.DataFrame, req: StrategyRequest) -> tuple[float, list[float], list[dict], list[dict]]:
    """Walk the price series applying entry/exit rules; return final capital, equity curve, trades, chart signals."""
    capital = 10_000.0
    equity: list[float] = [capital]
    trades: list[dict] = []
    signals: list[dict] = []   # chart markers
    in_trade = False
    entry_price = 0.0

    for i in range(1, len(df)):
        prev_cross = df["cross"].iloc[i - 1]
        curr_cross = df["cross"].iloc[i]
        price      = float(df["Close"].iloc[i])
        date_str   = str(df.index[i].date())
        rsi_val    = df["rsi"].iloc[i]

        # ── ENTRY (cross UP) ────────────────────────────────────────────────
        if not in_trade and curr_cross == 1 and prev_cross == 0:
            # RSI filter: skip if overbought
            if req.use_rsi_filter and not pd.isna(rsi_val) and rsi_val > 70:
                equity.append(capital)
                continue
            # Trend filter: skip if below long-term MA
            if req.use_trend_filter:
                trend_val = df["trend_ma"].iloc[i]
                if not pd.isna(trend_val) and price < trend_val:
                    equity.append(capital)
                    continue
            in_trade = True
            entry_price = price + req.spread + req.slippage
            signals.append({"date": date_str, "type": "buy", "price": round(entry_price, 4)})

        # ── EXIT (cross DOWN or RSI overbought) ─────────────────────────────
        elif in_trade and (
            (curr_cross == 0 and prev_cross == 1)
            or (req.use_rsi_filter and not pd.isna(rsi_val) and rsi_val > 78)
        ):
            exit_price = max(price - req.spread - req.slippage, 0.0)
            pnl_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else 0
            position_value = capital * req.risk_per_trade
            commission = position_value * req.commission_rate * 2
            trade_pnl = position_value * pnl_pct * req.reward_ratio - commission
            capital += trade_pnl
            is_win = trade_pnl > 0
            trades.append({
                "date":   date_str,
                "pnl":    round(trade_pnl, 2),
                "is_win": is_win,
                "entry":  round(entry_price, 4),
                "exit":   round(exit_price, 4),
                "costs":  round(commission, 2),
            })
            signals.append({"date": date_str, "type": "sell", "price": round(exit_price, 4)})
            in_trade = False

        equity.append(capital)

    return capital, equity, trades, signals


def _compute_streaks(trades: list[dict]) -> tuple[int, int, int]:
    """Return (max_win_streak, max_loss_streak, current_streak) from a sequence of trades."""
    if not trades:
        return 0, 0, 0

    streaks, cur = [], 1
    for i in range(1, len(trades)):
        if trades[i]["is_win"] == trades[i - 1]["is_win"]:
            cur += 1
        else:
            streaks.append(cur * (1 if trades[i - 1]["is_win"] else -1))
            cur = 1
    streaks.append(cur * (1 if trades[-1]["is_win"] else -1))

    max_win_streak  = max((s for s in streaks if s > 0), default=0)
    max_loss_streak = min((s for s in streaks if s < 0), default=0)
    current_streak  = streaks[-1]
    return max_win_streak, max_loss_streak, current_streak


def _run_backtest_on_history(hist: pd.DataFrame, req: StrategyRequest) -> dict:
    """
    Improved MA-crossover strategy with optional RSI and trend filters, run against
    already-fetched price history — lets a parameter sweep reuse a single download.

    Improvements over naive MA-cross:
    - RSI filter: skip BUY if RSI>70 (overbought), skip SELL if RSI<30 (oversold).
    - Trend filter: only BUY when price > slow_ma (uptrend confirmed).
    - Signals list: buy/sell markers with date + price for chart overlay.
    """
    if req.strategy == "rsi":
        df = _prepare_rsi_backtest_frame(hist, req)
        capital, equity, trades, signals = _simulate_rsi_trades(df, req)
    else:
        df = _prepare_backtest_frame(hist, req)
        capital, equity, trades, signals = _simulate_trades(df, req)

    equity_curve = [
        {"time": str(df.index[i].date()), "value": round(eq, 2)}
        for i, eq in enumerate(equity)
    ]

    wins   = [t for t in trades if t["is_win"]]
    losses = [t for t in trades if not t["is_win"]]
    win_rate = len(wins) / len(trades) if trades else 0

    eq_arr = np.array(equity)
    peak = np.maximum.accumulate(eq_arr)
    drawdown = (eq_arr - peak) / peak
    max_drawdown = float(drawdown.min())

    max_win_streak, max_loss_streak, current_streak = _compute_streaks(trades)

    total_profit    = capital - 10_000.0
    total_return_pct = (capital / 10_000.0 - 1) * 100
    # Sharpe-like score for optimization ranking
    eq_returns = pd.Series(equity).pct_change().dropna()
    strategy_sharpe = (
        float(eq_returns.mean() / eq_returns.std() * (252 ** 0.5))
        if eq_returns.std() > 0 else 0.0
    )

    return {
        "total_profit":      round(total_profit, 2),
        "total_return_pct":  round(total_return_pct, 2),
        "win_rate":          round(win_rate, 4),
        "num_trades":        len(trades),
        "max_drawdown":      round(max_drawdown, 4),
        "strategy_sharpe":   round(strategy_sharpe, 3),
        "equity_curve":      equity_curve,
        "trades":            trades[-40:],
        "all_trades":        trades,
        "signals":           signals,   # buy/sell markers for chart
        "stats": {
            "wins":             len(wins),
            "losses":           len(losses),
            "max_win_streak":   max_win_streak,
            "max_loss_streak":  abs(max_loss_streak),
            "current_streak":   current_streak,
        },
    }


def _run_backtest(req: StrategyRequest) -> dict:
    hist = _fetch_price_history(req.ticker, req.period)
    return _run_backtest_on_history(hist, req)


@app.post("/api/strategy/backtest")
async def strategy_backtest(req: StrategyRequest):
    try:
        result = await asyncio.to_thread(_run_backtest, req)
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


class OptimizeRequest(BaseModel):
    ticker: str
    period: str = "1y"
    strategy: str = "ma_cross"     # "ma_cross" | "rsi"
    risk_per_trade: float = 0.02
    reward_ratio: float = 2.0
    spread: float = Field(default=0.0, ge=0.0)
    slippage: float = Field(default=0.0, ge=0.0)
    commission_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    use_rsi_filter: bool = True
    use_trend_filter: bool = True
    top_n: int = 10


def _composite_score(bt: dict) -> float:
    """Return-per-drawdown score, damped by a trade-count confidence factor.

    Without this, a config validated on just 1-2 trades and a tiny drawdown
    can score far higher than one with a dozen trades and a strong win rate,
    simply for having gotten lucky on a statistically insignificant sample.
    Full confidence kicks in at >=10 trades; below that the raw score is
    scaled down proportionally.
    """
    dd = abs(bt["max_drawdown"]) or 0.01
    raw = (bt["total_return_pct"] * bt["win_rate"]) / dd
    confidence = min(bt["num_trades"] / 10, 1.0)
    return raw * confidence


@app.post("/api/strategy/optimize")
async def strategy_optimize(req: OptimizeRequest):
    """
    Grid search over strategy parameter combinations (MA crossover or RSI mean-reversion).
    Returns top_n configurations ranked by a composite score.
    """
    SHORT_MAS = [3, 5, 8, 10, 13, 15, 20, 21, 25, 30, 34]
    LONG_MAS  = [20, 30, 34, 40, 50, 60, 70, 89, 100, 120, 144, 150, 200]
    RSI_PERIODS      = [5, 10, 15, 20]
    OVERSOLD_LEVELS  = [20, 25, 30, 35, 40]
    OVERBOUGHT_LEVELS = [55, 60, 65, 70, 75]

    def _optimize(req: OptimizeRequest):
        hist = _fetch_price_history(req.ticker, req.period)
        results = []

        if req.strategy == "rsi":
            for rp in RSI_PERIODS:
                for os_ in OVERSOLD_LEVELS:
                    for ob in OVERBOUGHT_LEVELS:
                        try:
                            bt = _run_backtest_on_history(hist, StrategyRequest(
                                ticker=req.ticker,
                                period=req.period,
                                strategy="rsi",
                                rsi_period=rp,
                                rsi_oversold=os_,
                                rsi_overbought=ob,
                                risk_per_trade=req.risk_per_trade,
                                spread=req.spread,
                                slippage=req.slippage,
                                commission_rate=req.commission_rate,
                            ))
                            if bt["num_trades"] < 2:
                                continue
                            score = _composite_score(bt)
                            results.append({
                                "rsi_period":   rp,
                                "oversold":     os_,
                                "overbought":   ob,
                                "total_profit": bt["total_profit"],
                                "total_return": round(bt["total_return_pct"], 2),
                                "win_rate":     round(bt["win_rate"] * 100, 1),
                                "num_trades":   bt["num_trades"],
                                "max_drawdown": round(bt["max_drawdown"] * 100, 2),
                                "sharpe":       bt["strategy_sharpe"],
                                "score":        round(score, 3),
                            })
                        except Exception:
                            continue
        else:
            for sm in SHORT_MAS:
                for lm in LONG_MAS:
                    if lm <= sm:
                        continue
                    try:
                        bt = _run_backtest_on_history(hist, StrategyRequest(
                            ticker=req.ticker,
                            period=req.period,
                            strategy="ma_cross",
                            short_ma=sm,
                            long_ma=lm,
                            risk_per_trade=req.risk_per_trade,
                            reward_ratio=req.reward_ratio,
                            spread=req.spread,
                            slippage=req.slippage,
                            commission_rate=req.commission_rate,
                            use_rsi_filter=req.use_rsi_filter,
                            use_trend_filter=req.use_trend_filter,
                        ))
                        if bt["num_trades"] < 2:
                            continue
                        score = _composite_score(bt)
                        results.append({
                            "short_ma":     sm,
                            "long_ma":      lm,
                            "total_profit": bt["total_profit"],
                            "total_return": round(bt["total_return_pct"], 2),
                            "win_rate":     round(bt["win_rate"] * 100, 1),
                            "num_trades":   bt["num_trades"],
                            "max_drawdown": round(bt["max_drawdown"] * 100, 2),
                            "sharpe":       bt["strategy_sharpe"],
                            "score":        round(score, 3),
                        })
                    except Exception:
                        continue

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[: req.top_n]

    try:
        result = await asyncio.to_thread(_optimize, req)
        return {"results": result}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.get("/api/cache/stats/{ticker}")
async def cache_stats_endpoint(ticker: str):
    """Return cache coverage for a ticker across all intervals."""
    try:
        return {"ticker": ticker.upper(), "intervals": cache_stats(ticker)}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/api/cache/download/{ticker}")
async def trigger_cache_download(ticker: str):
    """Trigger background download of all intervals for a ticker."""
    try:
        background_download_all(ticker.upper())
        return {"status": "started", "ticker": ticker.upper()}
    except Exception as exc:
        raise HTTPException(500, str(exc))


# Serve SPA — must be last
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import errno
    import os

    requested_port = int(os.environ.get("ETF_PORT", 8000))
    ports = [requested_port, requested_port + 1, requested_port + 2]

    for port in ports:
        try:
            uvicorn.run(
                "server:app",
                host="0.0.0.0",
                port=port,
                log_level="info",
                reload=False,
            )
            break
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                raise
            print(f"Porta {port} occupata, provo la successiva...")
    else:
        raise RuntimeError(f"Nessuna porta disponibile: {ports}")
