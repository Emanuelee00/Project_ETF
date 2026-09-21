"""Grafo LangGraph: ciclo agentico di raccolta notizie + analisi sentiment sull'oro."""

from langgraph.graph import END, StateGraph

import config
import storage
from llm_sentiment import analyze_sentiment
from news_fetcher import fetch_gold_news
from state import GoldAgentState


def fetch_news_node(state: GoldAgentState) -> dict:
    tried = state.get("tickers_tried", [])
    remaining = [t for t in config.GOLD_TICKERS if t not in tried]
    ticker = remaining[0] if remaining else config.GOLD_TICKERS[-1]

    new_articles = fetch_gold_news(ticker)
    existing_titles = {a["title"] for a in state.get("articles", [])}
    merged = state.get("articles", []) + [a for a in new_articles if a["title"] not in existing_titles]

    return {
        "articles": merged,
        "tickers_tried": tried + [ticker],
        "attempts": state.get("attempts", 0) + 1,
    }


def should_fetch_more(state: GoldAgentState) -> str:
    """Routing del ciclo: continua a raccogliere notizie finché non ce ne sono abbastanza
    o non sono stati esauriti i tentativi disponibili."""
    enough_articles = len(state.get("articles", [])) >= config.MIN_ARTICLES
    attempts_left = state.get("attempts", 0) < config.MAX_FETCH_ATTEMPTS
    if not enough_articles and attempts_left:
        return "fetch_news"
    return "analyze_sentiment"


def analyze_sentiment_node(state: GoldAgentState) -> dict:
    articles = state.get("articles", [])[: config.MAX_ARTICLES_TO_ANALYZE]
    analyzed = [{**article, **analyze_sentiment(article["title"], article["publisher"])} for article in articles]
    return {"analyzed": analyzed}


def aggregate_node(state: GoldAgentState) -> dict:
    analyzed = state.get("analyzed", [])
    overall = sum(a["score"] for a in analyzed) / len(analyzed) if analyzed else 0.0

    if overall >= config.BUY_THRESHOLD:
        signal = "BUY"
    elif overall <= config.SELL_THRESHOLD:
        signal = "SELL"
    else:
        signal = "HOLD"

    summary = (
        f"Analizzati {len(analyzed)} articoli sull'oro ({', '.join(state.get('tickers_tried', []))}). "
        f"Punteggio medio di sentiment: {overall:.1f} -> segnale {signal}."
    )

    return {"overall_score": round(overall, 1), "signal": signal, "summary": summary}


def persist_node(state: GoldAgentState) -> dict:
    """Salva la run odierna in SQLite, così lo storico si accumula giorno dopo giorno."""
    new_count = storage.save_run(
        state.get("analyzed", []),
        state.get("overall_score", 0.0),
        state.get("signal", "HOLD"),
    )
    return {"new_articles_saved": new_count}


def build_graph():
    graph = StateGraph(GoldAgentState)
    graph.add_node("fetch_news", fetch_news_node)
    graph.add_node("analyze_sentiment", analyze_sentiment_node)
    graph.add_node("aggregate", aggregate_node)
    graph.add_node("persist", persist_node)

    graph.set_entry_point("fetch_news")
    graph.add_conditional_edges(
        "fetch_news",
        should_fetch_more,
        {"fetch_news": "fetch_news", "analyze_sentiment": "analyze_sentiment"},
    )
    graph.add_edge("analyze_sentiment", "aggregate")
    graph.add_edge("aggregate", "persist")
    graph.add_edge("persist", END)

    return graph.compile()
