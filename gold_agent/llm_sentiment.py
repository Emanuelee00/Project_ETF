"""Analisi del sentiment di una notizia tramite un LLM locale (Ollama)."""

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

import config

_llm: ChatOllama | None = None


def _get_llm() -> ChatOllama:
    global _llm
    if _llm is None:
        _llm = ChatOllama(model=config.OLLAMA_MODEL, base_url=config.OLLAMA_BASE_URL, temperature=0)
    return _llm


SYSTEM_PROMPT = (
    "Sei un analista finanziario specializzato nel mercato dell'oro (XAU/USD). "
    "Per ogni titolo di notizia che ricevi, valuta il suo probabile impatto sul prezzo dell'oro. "
    "Rispondi SOLO con un oggetto JSON valido, senza testo aggiuntivo, nel formato:\n"
    '{"sentiment": "positive" | "negative" | "neutral", "score": <intero da -100 a 100>, '
    '"reasoning": "<motivazione in una frase>"}'
)


def _parse_response(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    payload = match.group(0) if match else text
    data = json.loads(payload)

    sentiment = data.get("sentiment", "neutral")
    if sentiment not in ("positive", "negative", "neutral"):
        sentiment = "neutral"

    score = int(max(-100, min(100, int(data.get("score", 0)))))
    reasoning = str(data.get("reasoning", "")).strip()
    return {"sentiment": sentiment, "score": score, "reasoning": reasoning}


def analyze_sentiment(title: str, publisher: str) -> dict:
    """Chiede all'LLM locale di valutare l'impatto di una notizia sul prezzo dell'oro."""
    user_prompt = f"Titolo: {title}\nFonte: {publisher or 'sconosciuta'}"
    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]

    try:
        response = _get_llm().invoke(messages)
        return _parse_response(response.content)
    except Exception as exc:
        return {"sentiment": "neutral", "score": 0, "reasoning": f"errore di analisi: {exc}"}
