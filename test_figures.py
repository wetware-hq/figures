from pathlib import Path
import polars as pl
from figures import build
FIX = Path("/workspace/wetware/figures-fixture/fixture_export.csv").read_text()

def test_rules():
    _, checks = build(FIX, "/tmp/g.html", as_at="2026-10-16T08:00:00")
    s, runs, fig = next(c for c in checks if c[0]["concept_id"][0] == "crp")
    absent = s.filter(pl.col("status") != "measured")["t"].to_list()
    # 1 segments = measured runs split by absences
    assert len(runs) == 2 and len(fig.axes[0].get_lines()) >= 2
    # 2 one plot, no secondary axes
    assert len(fig.axes) == 1  # single x/y axes only
    # 3 every measured row plotted, none dropped
    assert sum(len(r) for r in runs) == s.filter(pl.col("status") == "measured").height
    # 4 no plotted point inside an absence span
    assert not any(min(absent) <= p["t"] <= max(absent) for r in runs for p in r)
    # unit converted: 3.9 mg/dL -> 39 mg/L
    assert any(abs(p["v"] - 39) < 1e-9 for r in runs for p in r)

def test_inferred_break_not_recorded_gap():
    from figures import absences
    _, checks = build(FIX, "/tmp/g.html", as_at="2026-10-16T08:00:00")
    s, runs, _ = checks[0]
    assert len(absences(s)) == 1  # only the recorded absence; inferred breaks never enter the data

def test_journal_and_test_copies():
    build(FIX, "/tmp/j.html", mode="journal", as_at="2026-10-16T08:00:00")

def test_future_dated_result_refused():
    import pytest
    with pytest.raises(SystemExit, match="REFUSED"):
        build(FIX, "/tmp/f.html", as_at="2026-10-12T00:00:00")

def test_no_title_and_anchored_age():
    _, checks = build(FIX, "/tmp/g.html", as_at="2026-10-16T08:00:00")
    ax = checks[0][2].axes[0]
    assert ax.get_title() == ""
    assert any("48 h before data as-at 16 Oct 08:00" in x.get_text() for x in ax.texts)

def test_png_has_no_legend_text():
    build(FIX, "/tmp/gl.html", as_at="2026-10-16T08:00:00")
    from pathlib import Path
    assert Path("/tmp/gl/figure_1.png").exists() and "Read with the bedside" in Path("/tmp/gl/legends.md").read_text()
    svg = Path("/tmp/gl/figure_1.svg").read_text()
    assert "Read with the bedside" not in svg and "clinical team" not in svg
