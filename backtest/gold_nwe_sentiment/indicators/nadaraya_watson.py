"""Nadaraya-Watson Envelope, variante endpoint (no-repaint).

Porting fedele di static/indicators/nadaraya_watson.js (funzione `endpoint`) usata nel
grafico web, così la banda calcolata qui per il backtest è identica a quella mostrata
in UI — a differenza della variante "repainting", usa solo le barre già disponibili in
ogni istante, quindi è l'unica adatta a un backtest senza lookahead bias.
"""

import numpy as np


def _gaussian_weights(bandwidth: float, lookback: int) -> np.ndarray:
    lags = np.arange(lookback)
    return np.exp(-(lags ** 2) / (2 * bandwidth ** 2))


def endpoint_envelope(
    source: np.ndarray, bandwidth: float = 8, multiplier: float = 3, lookback: int = 500
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ritorna (line, upper, lower). I primi 2*lookback-2 valori sono NaN (serve storico)."""
    n = len(source)
    line = np.full(n, np.nan)
    errors = np.full(n, np.nan)
    weights = _gaussian_weights(bandwidth, lookback)

    for i in range(lookback - 1, n):
        window = source[i - lookback + 1 : i + 1][::-1]  # lag 0 = barra i, lag k = i-k
        mask = ~np.isnan(window)
        if not mask.any():
            continue
        weight_sum = weights[mask].sum()
        if weight_sum == 0:
            continue
        line[i] = np.dot(window[mask], weights[mask]) / weight_sum
        errors[i] = abs(source[i] - line[i])

    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    band_start = lookback * 2 - 2
    for i in range(band_start, n):
        window_err = np.nan_to_num(errors[i - lookback + 1 : i + 1])
        mae = window_err.sum() / lookback * multiplier
        upper[i] = line[i] + mae
        lower[i] = line[i] - mae

    return line, upper, lower


def endpoint_line_errors_fast(source: np.ndarray, bandwidth: float, lookback: int = 500) -> tuple[np.ndarray, np.ndarray]:
    """Come la parte 'line/errors' di endpoint_envelope ma vettorizzata via convoluzione —
    stesso risultato numerico, molto più veloce quando bisogna provare molti bandwidth
    diversi (grid search fine). Richiede `source` senza NaN (vero per i prezzi Close)."""
    n = len(source)
    weights = _gaussian_weights(bandwidth, lookback)
    weight_sum = weights.sum()

    conv = np.convolve(source, weights, mode="valid") / weight_sum
    line = np.full(n, np.nan)
    line[lookback - 1 :] = conv

    errors = np.full(n, np.nan)
    errors[lookback - 1 :] = np.abs(source[lookback - 1 :] - line[lookback - 1 :])
    return line, errors


def bands_from_line_errors(line: np.ndarray, errors: np.ndarray, multiplier: float, lookback: int) -> tuple[np.ndarray, np.ndarray]:
    """Data una 'line/errors' già calcolata, applica un moltiplicatore per ottenere le bande
    — a costo quasi nullo, così si può riusare la stessa line per molti multiplier diversi."""
    n = len(line)
    err_filled = np.nan_to_num(errors)
    cumsum = np.cumsum(np.insert(err_filled, 0, 0.0))
    rolling_sum = cumsum[lookback:] - cumsum[:-lookback]
    mae = rolling_sum / lookback * multiplier

    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    valid_from = lookback - 1
    upper[valid_from:] = line[valid_from:] + mae
    lower[valid_from:] = line[valid_from:] - mae

    band_start = lookback * 2 - 2
    upper[:band_start] = np.nan
    lower[:band_start] = np.nan
    return upper, lower
