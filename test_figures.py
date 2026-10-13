import pytest
from pathlib import Path
import polars as pl
from figures import build
FIX = (Path(__file__).parent / "fixtures" / "fixture_export.csv").read_text()

def test_rules():
    _, checks = build(FIX, "/tmp/g.html", as_at="1937-10-16T08:00:00")
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
    _, checks = build(FIX, "/tmp/g.html", as_at="1937-10-16T08:00:00")
    s, runs, _ = checks[0]
    assert len(absences(s)) == 1  # only the recorded absence; inferred breaks never enter the data

def test_journal_and_test_copies():
    _, j = build(FIX, "/tmp/j.html", mode="journal", as_at="1937-10-16T08:00:00")
    _, n = build(FIX, "/tmp/n.html", as_at="1937-10-16T08:00:00")
    jt = [t.get_text() for t in j[0][2].texts]
    nt = [t.get_text() for t in n[0][2].texts]
    assert any("NOT FOR CLINICAL USE" in t for t in jt)
    assert not any("NOT FOR CLINICAL USE" in t for t in nt)
    for ext in ("png", "svg", "pdf"):
        assert Path(f"/tmp/j/figure_1.{ext}").stat().st_size > 0

def test_future_dated_result_refused():
    import pytest
    with pytest.raises(SystemExit, match="REFUSED"):
        build(FIX, "/tmp/f.html", as_at="1937-10-12T00:00:00")

def test_no_title_and_anchored_age():
    _, checks = build(FIX, "/tmp/g.html", as_at="1937-10-16T08:00:00")
    ax = checks[0][2].axes[0]
    assert ax.get_title() == ""
    assert any("48 h before data as-at 16 Oct 08:00" in x.get_text() for x in ax.texts)

def test_png_has_no_legend_text():
    build(FIX, "/tmp/gl.html", as_at="1937-10-16T08:00:00")
    from pathlib import Path
    assert Path("/tmp/gl/figure_1.png").exists() and "Read with the bedside" in Path("/tmp/gl/legends.md").read_text()
    svg = Path("/tmp/gl/figure_1.svg").read_text()
    assert "clinical team" not in svg and "admission baseline" not in svg and "Read with the bedside" in svg  # only the capped footer

def test_mismatched_pair_refused():
    import pytest, shutil
    from figures import verify
    build(FIX, "/tmp/v1.html", as_at="1937-10-16T08:00:00"); assert verify("/tmp/v1")
    build(FIX, "/tmp/v2.html", as_at="1937-10-16T08:00:00")
    shutil.copy("/tmp/v2/figure_1.png", "/tmp/v1/figure_1.png")   # stale legend, new image
    with pytest.raises(SystemExit, match="REFUSED"): verify("/tmp/v1")


# ---------- top-level guard: any error -> one fixed line, row number only ----------
import subprocess, re, sys as _sys
_FIG = str(Path(__file__).parent / "figures.py")


def _run(tmp_path, paste):
    p = tmp_path / "paste.csv"; p.write_text(paste)
    return subprocess.run([_sys.executable, _FIG, str(p)], capture_output=True, text=True, cwd=tmp_path)


DIAG = r"Diagnostic: [A-Za-z_]\w*(/[A-Z_]+)? at (figures|clean)\.py:(\d+|unknown)"
TOKS = ("MRN", "SYNTH-7731", "CRP", "notatime", "Synthvalue", "mg/L", "Traceback", "local_label")


def test_guard_bad_rows_mrn_header_no_echo(tmp_path):
    paste = ("MRN,local_label,t,value,unit,device,derivation,status,gap_reason\n"
             "SYNTH-7731,CRP,notatime,180.0,mg/L,lab:core,assay,measured,\n"
             "SYNTH-7731,CRP,1937-10-02T08:00:00,Synthvalue,mg/L,lab:core,assay,measured,\n")
    r = _run(tmp_path, paste)
    assert r.returncode == 2 and r.stdout == ""
    first, diag = r.stderr.strip().splitlines()
    assert first == "Refused: row 1 doesn't match the expected layout."
    assert re.fullmatch(DIAG, diag)
    for tok in TOKS:
        assert tok not in r.stdout + r.stderr, tok
    assert list(tmp_path.iterdir()) == [tmp_path / "paste.csv"]


def test_mrn_header_paste_charts_through_clean(tmp_path):
    paste = ("MRN\tTest\tCollected\tResult\tUnits\n"
             "SYNTH-7734\tCRP\t1937-10-01 08:00\t180\tmg/L\n"
             "SYNTH-7734\tCRP\t1937-10-02 08:00\tnotanumber\tmg/L\n"
             "SYNTH-7734\tCRP\t1937-10-03 08:00\t90\tmg/L\n")
    r = _run(tmp_path, paste)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "gallery" / "index.html").exists() and "notanumber" not in r.stdout + r.stderr


@pytest.mark.parametrize("sep", ["|", ";"])
def test_other_separators_via_clean(tmp_path, sep):
    rows = ["patient", "test", "time", "result", "unit"], ["SYNTH-7735", "CRP", "1937-10-01 08:00", "180", "mg/L"], \
           ["SYNTH-7735", "CRP", "1937-10-02 08:00", "90", "mg/L"]
    r = _run(tmp_path, "\n".join(sep.join(x) for x in rows) + "\n")
    if sep == "|":
        assert r.returncode == 0, r.stderr
    else:                                  # clean.py does not split on ';': refused, no pasted text
        assert r.returncode == 2 and r.stderr.splitlines()[0].startswith("Refused:")
        assert "SYNTH-7735" not in r.stderr and "CRP" not in r.stderr


def test_guard_short_row(tmp_path):
    paste = ("MRN,local_label,t,value,unit\nSYNTH-7732,CRP,notatime,5,mg/L\nSYNTH-7732,CRP\n")
    r = _run(tmp_path, paste)
    assert r.returncode != 0 and r.stderr.splitlines()[0] == "Refused: row 1 doesn't match the expected layout."
    assert "SYNTH-7732" not in r.stderr and "MRN" not in r.stderr


def test_guard_no_row_known(tmp_path):
    r = _run(tmp_path, "MRN SYNTH-7733 only one line\n")
    assert r.returncode != 0 and r.stdout == ""
    assert r.stderr.splitlines()[0] == "Refused: no rows in the expected layout were found. Nothing was saved."
    assert re.fullmatch(DIAG, r.stderr.splitlines()[1])
    assert "SYNTH-7733" not in r.stderr and "MRN" not in r.stderr
    assert list(tmp_path.iterdir()) == [tmp_path / "paste.csv"]
