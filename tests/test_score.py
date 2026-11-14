import math

import numpy as np
import pytest

from conftest import flat, series, steady_rise
from scoring.score import (MIN_BARS, combine, label_for, max_drawdown, momentum_part, reason, scale,
                           score_stock, smart_part, steadiness_part, trend_part, volatility)


# ---------- building blocks ----------
def test_scale_is_linear_and_clamped():
    assert scale(0.0, -0.1, 0.1) == 50
    assert scale(0.05, -0.1, 0.1) == pytest.approx(75)
    assert scale(0.5, -0.1, 0.1) == 100
    assert scale(-0.5, -0.1, 0.1) == 0
    assert scale(0.30, 0.50, 0.10) == pytest.approx(50)  # reversed: lower volatility is better


@pytest.mark.parametrize("score,label", [(100, "Looks strong"), (70, "Looks strong"), (69.6, "Looks strong"),
                                         (69.4, "Mixed"), (40, "Mixed"), (39.4, "Looks weak"), (0, "Looks weak")])
def test_labels(score, label):
    assert label_for(score) == label


# ---------- trend ----------
def test_trend_flat_is_neutral():
    t = trend_part(flat())
    assert t["score"] == pytest.approx(50)


def test_trend_exact_numbers():
    c = series([100.0] * 299 + [110.0])
    t = trend_part(c)
    sma50, sma200 = (49 * 100 + 110) / 50, (199 * 100 + 110) / 200
    assert t["metrics"]["sma50"] == pytest.approx(sma50)
    assert t["metrics"]["sma200"] == pytest.approx(sma200)
    expected = (0.35 * scale(110 / sma200 - 1, -0.10, 0.10)
                + 0.30 * scale(110 / sma50 - 1, -0.05, 0.05)
                + 0.35 * scale(sma50 / sma200 - 1, -0.05, 0.05))
    assert t["score"] == pytest.approx(expected)


def test_trend_rising_beats_falling():
    assert trend_part(steady_rise())["score"] > 80
    assert trend_part(steady_rise(daily=-0.001))["score"] < 20


# ---------- momentum ----------
def test_momentum_same_as_market_is_50():
    c = steady_rise()
    assert momentum_part(c, c)["score"] == pytest.approx(50)


def test_momentum_exact_excess():
    bench = flat()
    stock = series([100.0] * 299 + [110.0])  # +10% over every period; market flat
    m = momentum_part(stock, bench)
    assert m["metrics"]["excess_6m"] == pytest.approx(0.10)
    assert m["score"] == pytest.approx(75)  # +10 points on a -20..+20 scale


# ---------- steadiness ----------
def test_steadiness_flat_is_perfect():
    assert steadiness_part(flat())["score"] == pytest.approx(100)


def test_drawdown_exact():
    c = series(list(np.linspace(50, 100, 150)) + list(np.linspace(100, 70, 50)) + list(np.linspace(70, 80, 100)))
    assert max_drawdown(c) == pytest.approx(-0.30)
    assert scale(-0.30, -0.40, 0.0) == pytest.approx(25)


def test_volatility_matches_definition():
    rng = np.random.default_rng(0)
    c = series(100 * np.cumprod(1 + rng.normal(0, 0.01, 300)))
    rets = np.diff(c.to_numpy()[-127:]) / c.to_numpy()[-127:-1]
    assert volatility(c) == pytest.approx(np.std(rets, ddof=1) * math.sqrt(252))


def test_jumpy_stock_is_less_steady():
    rng = np.random.default_rng(1)
    calm = series(100 * np.cumprod(1 + rng.normal(0.0003, 0.005, 300)))
    wild = series(100 * np.cumprod(1 + rng.normal(0.0003, 0.03, 300)))
    assert steadiness_part(calm)["score"] > steadiness_part(wild)["score"]


# ---------- smart money + combining ----------
def test_smart_part():
    assert smart_part(None) is None
    assert smart_part(0)["score"] == 50
    assert smart_part(3)["score"] == 80
    assert smart_part(-10)["score"] == 0


def test_combine_with_all_parts():
    total, used = combine({"trend": 100, "momentum": 0, "steadiness": 0, "smart": 0})
    assert total == pytest.approx(30)
    assert used == pytest.approx({"trend": 0.30, "momentum": 0.25, "steadiness": 0.25, "smart": 0.20})


def test_combine_reweights_without_smart_money():
    total, used = combine({"trend": 100, "momentum": 0, "steadiness": 0, "smart": None})
    assert sum(used.values()) == pytest.approx(1)
    assert used["trend"] == pytest.approx(0.375) and "smart" not in used
    assert total == pytest.approx(37.5)


def test_score_stock_end_to_end():
    r = score_stock(steady_rise(daily=0.002), flat())
    assert 0 <= r["score"] <= 100 and r["label"] == "Looks strong"
    weak = score_stock(steady_rise(daily=-0.002), flat())
    assert weak["label"] == "Looks weak"


def test_needs_enough_history():
    with pytest.raises(ValueError):
        score_stock(flat(MIN_BARS - 1), flat(MIN_BARS - 1))


def test_reason_sentence():
    r = score_stock(steady_rise(daily=0.002), flat())
    text = reason(r, median_vol=1.0)
    vs200 = r["parts"]["trend"]["metrics"]["vs200"]
    ex = r["parts"]["momentum"]["metrics"]["excess_6m"]
    assert text == (f"{vs200:.0%} above its long-term (200-day) average with an upward trend, "
                    f"beating the market by {ex:.0%} over 6 months, with below-average swings.")
    weak = reason(score_stock(steady_rise(daily=-0.002), flat()), median_vol=0.0)
    assert weak.startswith(f"{abs(trend_part(steady_rise(daily=-0.002))['metrics']['vs200']):.0%} below")
    assert "trailing the market by" in weak and weak.endswith("above-average swings.")
