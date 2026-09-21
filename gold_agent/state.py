"""Stato condiviso del grafo LangGraph per l'analisi sentiment sull'oro."""

from typing import TypedDict


class Article(TypedDict):
    title: str
    publisher: str
    link: str
    date: str


class AnalyzedArticle(Article):
    sentiment: str  # "positive" | "negative" | "neutral"
    score: int  # -100..100
    reasoning: str


class GoldAgentState(TypedDict, total=False):
    tickers_tried: list[str]
    articles: list[Article]
    analyzed: list[AnalyzedArticle]
    attempts: int
    overall_score: float
    signal: str
    summary: str
    new_articles_saved: int
