"""Track record: how did each day's "Looks strong" group actually do afterwards?

For every saved daily snapshot, take the stocks labelled "Looks strong" that
day, and measure their equal-weighted average return over the next
21 / 63 / 126 trading days (about 1 / 3 / 6 months), next to the S&P 500 (SPY)
over the same days. Horizons that haven't passed yet are left empty.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HORIZONS = {"1m": 21, "3m": 63, "6m": 126}


def forward_return(close: pd.Series, start: pd.Timestamp, days: int) -> float | None:
    if close is None or close.empty:
        return None
    pos = close.index.searchsorted(pd.Timestamp(start), side="right") - 1  # last bar on/before start
    if pos < 0 or pos + days >= len(close):
        return None
    return float(close.iloc[pos + days] / close.iloc[pos] - 1)


def build_track_record(snapshots: list[dict], closes: dict[str, pd.Series], bench: str = "SPY") -> dict:
    """snapshots: [{"date": "YYYY-MM-DD", "strong": [tickers]}], oldest first."""
    cohorts = []
    for snap in snapshots:
        row = {"date": snap["date"], "count": len(snap["strong"]), "tickers": snap["strong"]}
        for h, days in HORIZONS.items():
            rets = [r for t in snap["strong"]
                    if (r := forward_return(closes.get(t), snap["date"], days)) is not None]
            spy = forward_return(closes.get(bench), snap["date"], days)
            if rets and spy is not None:
                group = float(np.mean(rets))
                row[h] = {"group": group, "spy": spy, "excess": group - spy, "beat": group > spy}
            else:
                row[h] = None
        cohorts.append(row)

    summary = {}
    for h in HORIZONS:
        done = [c[h] for c in cohorts if c[h]]
        summary[h] = None if not done else {
            "cohorts": len(done),
            "avg_group": float(np.mean([d["group"] for d in done])),
            "avg_spy": float(np.mean([d["spy"] for d in done])),
            "avg_excess": float(np.mean([d["excess"] for d in done])),
            "pct_beat": float(np.mean([d["beat"] for d in done])),
            "worst_excess": float(min(d["excess"] for d in done)),
            "best_excess": float(max(d["excess"] for d in done)),
        }
    return {"horizons": HORIZONS, "summary": summary, "cohorts": list(reversed(cohorts)),
            "tracking_since": snapshots[0]["date"] if snapshots else None}
