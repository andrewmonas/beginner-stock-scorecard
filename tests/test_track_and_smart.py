from datetime import date

import pytest

from conftest import flat, series, steady_rise
from scoring.smart_money import net_activity, normalize
from scoring.track import build_track_record, forward_return


# ---------- track record ----------
def test_forward_return_exact():
    c = series(range(100, 400))  # +1 per day
    start = c.index[10]
    assert forward_return(c, start, 21) == pytest.approx(131 / 110 - 1)


def test_forward_return_not_yet_known():
    c = series(range(100, 130))
    assert forward_return(c, c.index[-5], 21) is None


def test_track_record_counts_wins_and_losses():
    spy = flat(300)                      # market flat
    winner = steady_rise(300, 0.002)     # goes up
    loser = steady_rise(300, -0.002)     # goes down
    d1, d2 = str(spy.index[50].date()), str(spy.index[60].date())
    tr = build_track_record(
        [{"date": d1, "strong": ["WIN"]}, {"date": d2, "strong": ["LOSE"]}],
        {"SPY": spy, "WIN": winner, "LOSE": loser},
    )
    by_date = {c["date"]: c for c in tr["cohorts"]}
    assert by_date[d1]["1m"]["beat"] is True
    assert by_date[d2]["1m"]["beat"] is False          # the bad days are shown too
    s = tr["summary"]["1m"]
    assert s["cohorts"] == 2 and s["pct_beat"] == pytest.approx(0.5)
    assert s["worst_excess"] < 0 < s["best_excess"]
    assert tr["tracking_since"] == d1


def test_track_record_empty_before_launch():
    tr = build_track_record([], {"SPY": flat()})
    assert tr["cohorts"] == [] and tr["summary"]["1m"] is None


def test_track_record_recent_snapshot_has_no_result_yet():
    spy = flat(300)
    tr = build_track_record([{"date": str(spy.index[-3].date()), "strong": ["SPY"]}], {"SPY": spy})
    assert tr["cohorts"][0]["1m"] is None


# ---------- smart money parsing ----------
def test_normalize_insider_codes():
    rows = [{"Ticker": "AAPL", "Date": "2025-06-01", "TransactionCode": "P"},
            {"Ticker": "AAPL", "Date": "2025-06-02", "TransactionCode": "S"},
            {"Ticker": "AAPL", "Date": "2025-06-03", "TransactionCode": "A"},   # award: ignored
            {"Ticker": None, "Date": "2025-06-03", "TransactionCode": "P"}]     # bad row: ignored
    out = normalize(rows, "insider")
    assert [t["direction"] for t in out] == [1, -1]


def test_normalize_congress():
    rows = [{"Ticker": "msft", "TransactionDate": "2025-05-01", "Transaction": "Purchase"},
            {"Ticker": "MSFT", "TransactionDate": "2025-05-02", "Transaction": "Sale (Partial)"},
            {"Ticker": "MSFT", "TransactionDate": "2025-05-03", "Transaction": "Exchange"}]
    out = normalize(rows, "congress")
    assert [(t["ticker"], t["direction"]) for t in out] == [("MSFT", 1), ("MSFT", -1)]


def test_net_activity_90_day_window():
    trades = normalize([
        {"Ticker": "X", "Date": "2025-06-30", "TransactionCode": "P"},
        {"Ticker": "X", "Date": "2025-04-15", "TransactionCode": "P"},
        {"Ticker": "X", "Date": "2025-03-01", "TransactionCode": "S"},   # older than 90 days
        {"Ticker": "Y", "Date": "2025-06-30", "TransactionCode": "S"},   # other ticker
    ], "insider")
    assert net_activity(trades, "X", date(2025, 6, 30)) == 2
