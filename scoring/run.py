"""Daily job: fetch prices, score every ticker, write JSON for the website.

    python -m scoring.run           # real data (needs ALPACA_API_KEY / ALPACA_SECRET_KEY)
    python -m scoring.run --demo    # fake prices, for previewing the site only
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from . import smart_money
from .data import demo_closes, fetch_alpaca_closes, load_universe
from .score import MIN_BARS, SMART_DAYS, WEIGHTS, combine, method_description, reason, score_stock
from .track import build_track_record

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "site" / "data"
BENCH = "SPY"
HISTORY_DAYS = 30
CHART_DAYS = 260


def clean(obj):
    """Round floats and turn NaN into null so the JSON is small and valid."""
    if isinstance(obj, float):
        return None if math.isnan(obj) or math.isinf(obj) else round(obj, 4)
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    return obj


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(data), separators=(",", ":")), encoding="utf-8")


def smart_money_setup(demo: bool) -> tuple[list[dict] | None, str]:
    flag = os.getenv("ENABLE_SMART_MONEY", "auto").strip().lower()
    key = os.getenv("QUIVER_API_KEY", "").strip()
    if demo:
        return None, "Off in demo mode."
    if flag in ("false", "0", "no", "off"):
        return None, "Switched off (ENABLE_SMART_MONEY=false)."
    if not key:
        return None, "Off: no Quiver Quant API key provided."
    try:
        trades = smart_money.fetch_trades(key)
        return trades, f"On: {len(trades)} recent insider/congress trades loaded from Quiver Quant."
    except Exception as e:  # never let the optional signal break the daily run
        print(f"WARNING: smart money disabled for this run: {e}", file=sys.stderr)
        return None, "Off today: the Quiver Quant data could not be loaded."


def load_snapshots(hist_dir: Path) -> list[dict]:
    snaps = []
    for f in sorted(hist_dir.glob("????-??-??.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        snaps.append({"date": s["date"], "strong": s.get("strong", [])})
    return snaps


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use fake prices (preview only)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    out: Path = args.out
    universe = load_universe()
    symbols = [u["ticker"] for u in universe]
    hist_dir = out / "history"
    prior = load_snapshots(hist_dir) if not args.demo else []

    # ---- prices ----
    if args.demo:
        closes = demo_closes(symbols)
    else:
        key, secret = os.getenv("ALPACA_API_KEY", "").strip(), os.getenv("ALPACA_SECRET_KEY", "").strip()
        if not key or not secret:
            print("ERROR: set ALPACA_API_KEY and ALPACA_SECRET_KEY (see README).", file=sys.stderr)
            return 2
        start = date.today() - timedelta(days=600)
        if prior:
            start = min(start, date.fromisoformat(prior[0]["date"]) - timedelta(days=10))
        closes = fetch_alpaca_closes(symbols, key, secret, start, feed=os.getenv("DATA_FEED", "iex"))
    if BENCH not in closes:
        print("ERROR: no S&P 500 (SPY) prices, cannot score.", file=sys.stderr)
        return 3
    bench = closes[BENCH]
    asof = bench.index[-1]

    trades, smart_note = smart_money_setup(args.demo)

    # ---- score today ----
    results, skipped = [], []
    for u in universe:
        t = u["ticker"]
        c = closes.get(t)
        if c is None or len(c.loc[:asof]) < MIN_BARS:
            skipped.append(t)
            continue
        c = c.loc[:asof]
        net = (smart_money.net_activity(trades, t, asof.date(), SMART_DAYS)
               if trades is not None and u["type"] == "stock" else None)
        r = score_stock(c, bench, net)
        results.append((u, c, r))

    median_vol = statistics.median(r["parts"]["steadiness"]["metrics"]["volatility"] for _, _, r in results)

    # ---- per-ticker files ----
    stocks_dir = out / "stocks"
    shutil.rmtree(stocks_dir, ignore_errors=True)
    rows = []
    hist_dates = bench.index[-HISTORY_DAYS:]
    for u, c, r in results:
        t = u["ticker"]
        history = []
        for d in hist_dates:
            cd = c.loc[:d]
            if len(cd) < MIN_BARS:
                continue
            net = (smart_money.net_activity(trades, t, d.date(), SMART_DAYS)
                   if trades is not None and u["type"] == "stock" else None)
            h = score_stock(cd, bench.loc[:d], net)
            history.append({"date": d.date().isoformat(), "score": h["score"],
                            **{k: (v["score"] if v else None) for k, v in h["parts"].items()}})
        row = {
            "ticker": t, "name": u["name"], "sector": u["sector"], "type": u["type"],
            "score": round(r["score"]), "score_exact": r["score"], "label": r["label"],
            "parts": {k: (v["score"] if v else None) for k, v in r["parts"].items()},
            "reason": reason(r, median_vol),
            "price": r["parts"]["trend"]["metrics"]["price"],
            "volatility": r["parts"]["steadiness"]["metrics"]["volatility"],
            "max_drawdown": r["parts"]["steadiness"]["metrics"]["max_drawdown"],
            "ret_6m": r["parts"]["momentum"]["metrics"]["ret_6m"],
            "spark": c.iloc[-90:].round(2).tolist(),
        }
        rows.append(row)
        chart = pd.DataFrame({"close": c, "sma50": c.rolling(50).mean(), "sma200": c.rolling(200).mean()}).iloc[-CHART_DAYS:]
        write_json(stocks_dir / f"{t}.json", {
            **row,
            "details": {k: v for k, v in r["parts"].items()},
            "weights_used": r["weights_used"],
            "chart": {"dates": [d.date().isoformat() for d in chart.index],
                      **{col: chart[col].round(2).tolist() for col in chart.columns}},
            "history": history,
        })

    strong = sorted((x for x in rows if x["label"] == "Looks strong"), key=lambda x: -x["score_exact"])
    steady = sorted(rows, key=lambda x: -x["parts"]["steadiness"])
    asof_s = asof.date().isoformat()

    write_json(out / "latest.json", {
        "asof": asof_s,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "demo": args.demo,
        "smart_money": {"enabled": trades is not None, "note": smart_note},
        "weights_used": combine({k: 1.0 for k in WEIGHTS if k != "smart" or trades is not None})[1],
        "method": method_description(),
        "median_volatility": median_vol,
        "counts": {lab: sum(1 for x in rows if x["label"] == lab) for lab in ("Looks strong", "Mixed", "Looks weak")},
        "top_strong": [x["ticker"] for x in strong[:10]],
        "top_steady": [x["ticker"] for x in steady[:10]],
        "skipped": skipped,
        "stocks": [{k: v for k, v in x.items() if k != "score_exact"} for x in rows],
    })

    # ---- daily snapshot + track record (real data only) ----
    if args.demo:
        if not (out / "track_record.json").exists():
            write_json(out / "track_record.json", build_track_record([], closes))
    else:
        write_json(hist_dir / f"{asof_s}.json", {
            "date": asof_s, "strong": [x["ticker"] for x in strong],
            "scores": {x["ticker"]: {"score": x["score"], "label": x["label"], "close": x["price"]} for x in rows},
        })
        snaps = load_snapshots(hist_dir)
        write_json(hist_dir / "index.json", [s["date"] for s in snaps])
        write_json(out / "track_record.json", build_track_record(snaps, closes))

    print(f"Scored {len(rows)} tickers as of {asof_s} "
          f"({'DEMO data' if args.demo else 'Alpaca data'}); skipped: {skipped or 'none'}. "
          f"Smart money: {smart_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
