from pathlib import Path
import polars as pl
from figures import build
FIX = Path("/workspace/wetware/figures-fixture/fixture_export.csv").read_text()

def test_rules():
    _, checks = build(FIX, "/tmp/g.html")
    s, runs, fig = next(c for c in checks if c[0]["concept_id"][0] == "crp")
    absent = s.filter(pl.col("status") != "measured")["t"].to_list()
    # 1 segments = measured runs split by absences
    assert len(runs) == 2 and len(fig.axes[0].get_lines()) >= 2
    # 2 tick strip exists
    assert len(fig.axes) == 2 and fig.axes[1].collections
    # 3 every measured row plotted, none dropped
    assert sum(len(r) for r in runs) == s.filter(pl.col("status") == "measured").height
    # 4 no plotted point inside an absence span
    assert not any(min(absent) <= p["t"] <= max(absent) for r in runs for p in r)
    # unit converted: 3.9 mg/dL -> 39 mg/L
    assert any(abs(p["v"] - 39) < 1e-9 for r in runs for p in r)

def test_inferred_break_not_recorded_gap():
    from figures import absences
    _, checks = build(FIX, "/tmp/g.html")
    s, runs, _ = checks[0]
    assert len(absences(s)) == 1  # only the recorded absence; inferred breaks never enter the data

def test_journal_and_test_copies():
    build(FIX, "/tmp/j.html", mode="journal"); build(FIX, "/tmp/t.html", mode="test")
