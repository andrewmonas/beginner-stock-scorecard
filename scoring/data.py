"""Price data: Alpaca (real) or a synthetic demo set (for previewing the site)."""
from __future__ import annotations

import csv
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

MARKET_TZ = ZoneInfo("America/New_York")
UNIVERSE_FILE = Path(__file__).with_name("universe.csv")


def load_universe(path: Path = UNIVERSE_FILE) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: v.strip() for k, v in row.items()} for row in csv.DictReader(f)]


def fetch_alpaca_closes(symbols: list[str], api_key: str, api_secret: str, start: date,
                        feed: str = "iex", chunk: int = 50) -> dict[str, pd.Series]:
    """Daily closing prices (split/dividend adjusted), indexed by trading date."""
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    client = StockHistoricalDataClient(api_key, api_secret)
    out: dict[str, pd.Series] = {}
    for i in range(0, len(symbols), chunk):
        req = StockBarsRequest(
            symbol_or_symbols=symbols[i:i + chunk],
            timeframe=TimeFrame.Day,
            start=datetime.combine(start, time.min, tzinfo=MARKET_TZ),
            feed=DataFeed.SIP if feed == "sip" else DataFeed.IEX,
            adjustment=Adjustment.ALL,
        )
        df = client.get_stock_bars(req).df
        if df.empty:
            continue
        for sym, g in df.groupby(level="symbol"):
            idx = pd.DatetimeIndex(g.index.get_level_values("timestamp"))
            if idx.tz is not None:
                idx = idx.tz_convert(MARKET_TZ).tz_localize(None)
            out[sym] = pd.Series(g["close"].to_numpy(dtype=float), index=idx.normalize(), name=sym).sort_index()
    return out


def demo_closes(symbols: list[str], end: date | None = None, days: int = 600) -> dict[str, pd.Series]:
    """Repeatable FAKE prices so the site can be previewed without an API key."""
    idx = pd.bdate_range(end=pd.Timestamp(end or date.today()), periods=days)
    market = np.random.default_rng(7).normal(0.0004, 0.010, days)
    out = {}
    for sym in symbols:
        rng = np.random.default_rng(sum((i + 1) * ord(c) for i, c in enumerate(sym)))
        beta, drift, noise = rng.uniform(0.6, 1.4), rng.normal(0, 0.0006), rng.uniform(0.004, 0.02)
        rets = beta * market + drift + rng.normal(0, noise, days)
        out[sym] = pd.Series(rng.uniform(30, 400) * np.exp(np.cumsum(rets)), index=idx, name=sym)
    return out
