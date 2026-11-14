"""The scoring method. Pure math: price series in, numbers out.

Every part is scored 0-100 with a straight-line scale between two anchor
points (see `scale`). The anchors and weights below are published on the site.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

WEIGHTS = {"trend": 0.30, "momentum": 0.25, "steadiness": 0.25, "smart": 0.20}

# Anchors: (value that scores 0, value that scores 100)
TREND_ANCHORS = {
    "vs200": (-0.10, 0.10),        # price 10% below its 200-day average -> 0, 10% above -> 100
    "vs50": (-0.05, 0.05),         # price 5% below its 50-day average -> 0, 5% above -> 100
    "sma50_vs_200": (-0.05, 0.05), # 50-day average 5% below the 200-day -> 0, 5% above -> 100
}
TREND_SUBWEIGHTS = {"vs200": 0.35, "vs50": 0.30, "sma50_vs_200": 0.35}
MOMENTUM_PERIODS = {"3m": 63, "6m": 126, "12m": 252}  # trading days
MOMENTUM_ANCHORS = (-0.20, 0.20)    # 20 points behind the S&P 500 -> 0, 20 points ahead -> 100
VOL_WINDOW = 126                    # ~6 months of daily moves
VOL_ANCHORS = (0.50, 0.10)          # 50% yearly volatility -> 0, 10% -> 100
DD_WINDOW = 252                     # ~1 year
DD_ANCHORS = (-0.40, 0.0)           # 40% drop from a high -> 0, no drop -> 100
SMART_DAYS = 90
SMART_POINTS_PER_TRADE = 10         # 50 is neutral; each net purchase +10, each net sale -10
LABELS = [(70, "Looks strong"), (40, "Mixed"), (0, "Looks weak")]
MIN_BARS = max(MOMENTUM_PERIODS.values()) + 1  # 253 trading days of history needed


def scale(x: float, at_zero: float, at_hundred: float) -> float:
    """Map x onto 0-100 in a straight line, clamped at the ends."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return float("nan")
    s = (x - at_zero) / (at_hundred - at_zero) * 100
    return float(min(100.0, max(0.0, s)))


def label_for(score: float) -> str:
    s = round(score)
    for threshold, name in LABELS:
        if s >= threshold:
            return name
    return LABELS[-1][1]


def trend_part(close: pd.Series) -> dict:
    price = float(close.iloc[-1])
    sma50 = float(close.iloc[-50:].mean())
    sma200 = float(close.iloc[-200:].mean())
    m = {"price": price, "sma50": sma50, "sma200": sma200,
         "vs50": price / sma50 - 1, "vs200": price / sma200 - 1, "sma50_vs_200": sma50 / sma200 - 1}
    sub = {k: scale(m[k], *TREND_ANCHORS[k]) for k in TREND_ANCHORS}
    score = sum(sub[k] * w for k, w in TREND_SUBWEIGHTS.items())
    return {"score": score, "sub": sub, "metrics": m}


def period_return(close: pd.Series, days: int) -> float:
    return float(close.iloc[-1] / close.iloc[-1 - days] - 1)


def momentum_part(close: pd.Series, bench: pd.Series) -> dict:
    bench = bench.reindex(close.index).ffill()
    m, sub = {}, {}
    for name, days in MOMENTUM_PERIODS.items():
        r, b = period_return(close, days), period_return(bench, days)
        m[f"ret_{name}"], m[f"bench_{name}"], m[f"excess_{name}"] = r, b, r - b
        sub[name] = scale(r - b, *MOMENTUM_ANCHORS)
    return {"score": float(np.mean(list(sub.values()))), "sub": sub, "metrics": m}


def volatility(close: pd.Series, window: int = VOL_WINDOW) -> float:
    rets = close.pct_change().iloc[-window:]
    return float(rets.std(ddof=1) * math.sqrt(252))


def max_drawdown(close: pd.Series, window: int = DD_WINDOW) -> float:
    w = close.iloc[-window:]
    return float((w / w.cummax() - 1).min())


def steadiness_part(close: pd.Series) -> dict:
    vol, dd = volatility(close), max_drawdown(close)
    sub = {"volatility": scale(vol, *VOL_ANCHORS), "drawdown": scale(dd, *DD_ANCHORS)}
    return {"score": (sub["volatility"] + sub["drawdown"]) / 2, "sub": sub,
            "metrics": {"volatility": vol, "max_drawdown": dd}}


def smart_part(net: int | None) -> dict | None:
    if net is None:
        return None
    return {"score": float(min(100, max(0, 50 + SMART_POINTS_PER_TRADE * net))), "sub": {},
            "metrics": {"net_trades": int(net)}}


def combine(part_scores: dict[str, float | None], weights: dict[str, float] = WEIGHTS) -> tuple[float, dict]:
    """Weighted average of the parts that exist; missing parts are dropped and
    the remaining weights are scaled up so they still add to 100%."""
    active = {k: w for k, w in weights.items() if part_scores.get(k) is not None}
    total = sum(active.values())
    used = {k: w / total for k, w in active.items()}
    return sum(part_scores[k] * w for k, w in used.items()), used


def score_stock(close: pd.Series, bench: pd.Series, smart_net: int | None = None) -> dict:
    close = close.dropna().astype(float)
    if len(close) < MIN_BARS:
        raise ValueError(f"need {MIN_BARS} days of prices, got {len(close)}")
    parts = {
        "trend": trend_part(close),
        "momentum": momentum_part(close, bench.astype(float)),
        "steadiness": steadiness_part(close),
        "smart": smart_part(smart_net),
    }
    total, used = combine({k: (v["score"] if v else None) for k, v in parts.items()})
    return {"score": total, "label": label_for(total), "parts": parts, "weights_used": used}


def reason(result: dict, median_vol: float) -> str:
    """One plain-English sentence. Never uses action words like buy/sell."""
    t = result["parts"]["trend"]["metrics"]
    m = result["parts"]["momentum"]["metrics"]
    vol = result["parts"]["steadiness"]["metrics"]["volatility"]
    dist = f"{abs(t['vs200']):.0%}"
    if t["vs200"] >= 0:
        trend = f"{dist} above its long-term (200-day) average" + (" with an upward trend" if t["sma50_vs_200"] > 0 else "")
    else:
        trend = f"{dist} below its long-term (200-day) average" + (" and trending down" if t["sma50_vs_200"] < 0 else "")
    ex = m["excess_6m"]
    if ex > 0.02:
        mom = f"beating the market by {ex:.0%} over 6 months"
    elif ex < -0.02:
        mom = f"trailing the market by {-ex:.0%} over 6 months"
    else:
        mom = "roughly matching the market over 6 months"
    steady = "with below-average swings" if vol <= median_vol else "with above-average swings"
    return f"{trend}, {mom}, {steady}."


def method_description() -> dict:
    """Published on the site so the explanation always matches the code."""
    return {
        "weights": WEIGHTS,
        "trend_anchors": TREND_ANCHORS, "trend_subweights": TREND_SUBWEIGHTS,
        "momentum_periods": MOMENTUM_PERIODS, "momentum_anchors": MOMENTUM_ANCHORS,
        "vol_window": VOL_WINDOW, "vol_anchors": VOL_ANCHORS,
        "dd_window": DD_WINDOW, "dd_anchors": DD_ANCHORS,
        "smart_days": SMART_DAYS, "smart_points_per_trade": SMART_POINTS_PER_TRADE,
        "labels": LABELS,
    }
