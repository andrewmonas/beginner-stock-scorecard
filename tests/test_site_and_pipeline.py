"""Checks on the whole pipeline (demo data) and on the website's wording."""
import json
import re

from conftest import ROOT
from scoring.run import main

FORBIDDEN = re.compile(r"\b(buy|buys|buying|sell|sells|selling|guaranteed|will go up)\b", re.I)
BANNER = "Educational information only, not financial advice."
SITE = ROOT / "site"


def test_demo_run_writes_site_data(tmp_path):
    assert main(["--demo", "--out", str(tmp_path)]) == 0
    latest = json.loads((tmp_path / "latest.json").read_text())
    assert latest["demo"] is True and latest["smart_money"]["enabled"] is False
    assert len(latest["stocks"]) >= 100
    assert abs(sum(latest["weights_used"].values()) - 1) < 1e-6
    for s in latest["stocks"]:
        assert 0 <= s["score"] <= 100
        assert s["label"] in ("Looks strong", "Mixed", "Looks weak")
        assert not FORBIDDEN.search(s["reason"]), s["reason"]
    one = json.loads((tmp_path / "stocks" / "AAPL.json").read_text())
    assert len(one["history"]) == 30 and len(one["chart"]["dates"]) == 260
    # demo data must never create track-record snapshots
    assert not (tmp_path / "history").exists()


def test_no_forbidden_words_on_site():
    files = list(SITE.glob("*.html")) + list((SITE / "js").glob("*.js"))
    assert files, "site files missing"
    for f in files:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            m = FORBIDDEN.search(line)
            assert not m, f"{f.name}:{i} uses '{m.group(0)}'"


def test_disclaimer_banner_on_every_page():
    for f in SITE.glob("*.html"):
        assert BANNER in f.read_text(encoding="utf-8"), f"banner missing on {f.name}"
