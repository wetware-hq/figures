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
    assert first == "Refused: no rows in the expected layout were found. Nothing was saved."
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
    else:
        assert r.returncode == 2
        assert r.stderr.splitlines()[0] == "Refused: semicolon-separated pastes aren't supported (row 2). Use commas or tabs."
        assert "SYNTH-7735" not in r.stderr and "CRP" not in r.stderr


def test_guard_short_row(tmp_path):
    paste = ("MRN,local_label,t,value,unit\nSYNTH-7732,CRP,notatime,5,mg/L\nSYNTH-7732,CRP\n")
    r = _run(tmp_path, paste)
    assert r.returncode != 0 and r.stderr.splitlines()[0] == "Refused: no rows in the expected layout were found. Nothing was saved."
    assert "SYNTH-7732" not in r.stderr and "MRN" not in r.stderr


def test_guard_no_row_known(tmp_path):
    r = _run(tmp_path, "MRN SYNTH-7733 only one line\n")
    assert r.returncode != 0 and r.stdout == ""
    assert r.stderr.splitlines()[0] == "Refused: no rows in the expected layout were found. Nothing was saved."
    assert re.fullmatch(DIAG, r.stderr.splitlines()[1])
    assert "SYNTH-7733" not in r.stderr and "MRN" not in r.stderr
    assert list(tmp_path.iterdir()) == [tmp_path / "paste.csv"]



# ---------- round 6: gaps, counts, censored and not-done markers (Educator wording) ----------
HEAD6 = "patient,test,time,result,unit,status\n"


def _gallery(tmp_path, body):
    r = _run(tmp_path, HEAD6 + body)
    assert r.returncode == 0, r.stderr
    return (tmp_path / "gallery" / "index.html").read_text(), (tmp_path / "gallery" / "legends.md").read_text(), r


def test_unreadable_row_with_time_becomes_gap_and_counted(tmp_path):
    page, leg, r = _gallery(tmp_path, "SYNTH-8001,CRP,1937-10-01 08:00,180,mg/L,final\n"
                                      "SYNTH-8001,CRP,1937-10-02 08:00,Synthjunk,mg/L,final\n"
                                      "SYNTH-8001,CRP,notatime,99,mg/L,final\n"
                                      "SYNTH-8001,CRP,1937-10-03 08:00,90,mg/L,final\n")
    assert "Gap: a result was recorded here but couldn&#x27;t be read." in page or \
           "Gap: a result was recorded here but couldn't be read." in page
    assert "2 rows couldn't be read and aren't shown: 1 is marked as a gap, 1 has no readable time." in leg
    assert "Synthjunk" not in page + leg + r.stdout + r.stderr and "notatime" not in page + leg


def test_count_line_omitted_when_zero(tmp_path):
    page, leg, _ = _gallery(tmp_path, "SYNTH-8002,CRP,1937-10-01 08:00,180,mg/L,final\n"
                                      "SYNTH-8002,CRP,1937-10-02 08:00,90,mg/L,final\n")
    assert "couldn't be read" not in leg and "class=count" not in page


def test_censored_markers_and_legends(tmp_path):
    page, leg, _ = _gallery(tmp_path, "SYNTH-8003,CRP,1937-10-01 08:00,180,mg/L,final\n"
                                      "SYNTH-8003,CRP,1937-10-02 08:00,<5,mg/L,final\n"
                                      "SYNTH-8003,CRP,1937-10-03 08:00,>300,mg/L,final\n")
    assert "▼ below the test's limit (<5). The real value is lower than shown." in leg
    assert "▲ above the test's limit (>300). The real value is higher than shown." in leg


def test_not_done_marker_legend(tmp_path):
    page, leg, _ = _gallery(tmp_path, "SYNTH-8004,CRP,1937-10-01 08:00,180,mg/L,final\n"
                                      "SYNTH-8004,CRP,1937-10-02 08:00,,mg/L,not done\n"
                                      "SYNTH-8004,CRP,1937-10-03 08:00,90,mg/L,final\n")
    assert "✕ Not done: no test was done at this time." in leg


def test_draw_uses_distinct_markers():
    from figures import build as b
    paste = (HEAD6 + "SYNTH-8005,CRP,1937-10-01 08:00,180,mg/L,final\nSYNTH-8005,CRP,1937-10-02 08:00,<5,mg/L,final\n"
             "SYNTH-8005,CRP,1937-10-03 08:00,,mg/L,missed\nSYNTH-8005,CRP,1937-10-04 08:00,90,mg/L,final\n")
    _, checks = b(paste, "/tmp/g6.html", as_at="1937-10-16T08:00:00")
    markers = {l.get_marker() for l in checks[0][2].axes[0].get_lines()}
    assert {"v", "x"} <= markers


# ---------- round 7 ----------
from figures import count_line


def test_count_line_grammar_and_parts():
    assert count_line(0, 0, 0, []) == ""
    assert count_line(1, 1, 0, []) == "1 row couldn't be read and isn't shown: 1 is marked as a gap."
    assert count_line(4, 2, 1, [7]) == ("4 rows couldn't be read and aren't shown: 2 are marked as gaps, "
                                        "1 has no readable time, 1 has a test name we didn't recognise (row 7).")
    assert count_line(5, 0, 3, [2, 4]) == ("5 rows couldn't be read and aren't shown: 3 have no readable time, "
                                           "2 have test names we didn't recognise (rows 2, 4).")


def test_unrecognised_test_name_counted_with_row(tmp_path):
    page, leg, r = _gallery(tmp_path, "SYNTH-8101,CRP,1937-10-01 08:00,180,mg/L,final\n"
                                      "SYNTH-8101,Synthwidget,1937-10-02 08:00,5,mg/L,final\n"
                                      "SYNTH-8101,CRP,1937-10-03 08:00,90,mg/L,final\n")
    assert "1 row couldn't be read and isn't shown: 1 has a test name we didn't recognise (row 3)." in leg
    assert "Synthwidget" not in page + leg + r.stdout + r.stderr


def test_not_done_cross_marker(tmp_path):
    page, leg, _ = _gallery(tmp_path, "SYNTH-8102,CRP,1937-10-01 08:00,180,mg/L,final\n"
                                      "SYNTH-8102,CRP,1937-10-02 08:00,,mg/L,not done\n"
                                      "SYNTH-8102,CRP,1937-10-03 08:00,90,mg/L,final\n")
    assert "✕ Not done: no test was done at this time." in leg and "○" not in leg


def test_test_without_normal_range_charted_and_flagged(tmp_path):
    page, leg, r = _gallery(tmp_path, "SYNTH-8103,Lactate,1937-10-01 08:00,2.1,mmol/L,final\n"
                                      "SYNTH-8103,Lactate,1937-10-02 08:00,1.4,mmol/L,final\n")
    flag = "Flag: no normal range on file for the test on row 2. It's charted without one."
    assert flag in r.stderr.splitlines()
    assert "figure_1.png" in page and "Interpretation withheld" in leg


def test_pipe_paste_unknown_column_refused_row_and_column(tmp_path):
    r = _run(tmp_path, "patient|test|time|result|Synthextra\nSYNTH-8104|CRP|1937-10-01 08:00|180|x\n")
    assert r.returncode == 2
    assert r.stderr.splitlines()[0] == "Refused: row 1, column 5 doesn't match the expected layout."
    assert "Synthextra" not in r.stderr and "SYNTH-8104" not in r.stderr


def test_pipe_paste_ambiguous_column_refused(tmp_path):
    r = _run(tmp_path, "patient|test|time|result|value\nSYNTH-8105|CRP|1937-10-01 08:00|180|90\n")
    assert r.returncode == 2
    assert r.stderr.splitlines()[0] == "Refused: row 1, column 5 doesn't match the expected layout."


def test_wide_paste_non_time_column_refused(tmp_path):
    r = _run(tmp_path, "patient\ttest\tunit\t1937-10-01 08:00\tSynthcol\nSYNTH-8106\tCRP\tmg/L\t180\t90\n")
    assert r.returncode == 2
    assert r.stderr.splitlines()[0] == "Refused: row 1, column 5 doesn't match the expected layout."
    assert "Synthcol" not in r.stderr


@pytest.mark.parametrize("sep", [",", "\t", "|"])
def test_swapped_time_and_value_columns_refused(tmp_path, sep):
    rows = [["patient", "test", "time", "result", "unit"],
            ["SYNTH-8107", "CRP", "180", "1937-10-01 08:00", "mg/L"],
            ["SYNTH-8107", "CRP", "90", "1937-10-02 08:00", "mg/L"]]
    r = _run(tmp_path, "\n".join(sep.join(x) for x in rows) + "\n")
    assert r.returncode == 2
    assert r.stderr.splitlines()[0] == "Refused: row 2, column 3 doesn't match the expected layout."
    assert "SYNTH-8107" not in r.stderr and list(tmp_path.iterdir()) == [tmp_path / "paste.csv"]


def test_semicolon_refusal_names_row(tmp_path):
    r = _run(tmp_path, "patient;test;time;result\nSYNTH-8108;CRP;1937-10-01 08:00;180\n")
    assert r.stderr.splitlines()[0] == "Refused: semicolon-separated pastes aren't supported (row 2). Use commas or tabs."


# ---------- round 8 ----------
def test_value_and_unit_swapped_refused_with_row_and_column(tmp_path):
    r = _run(tmp_path, "patient,local_label,t,value,unit\nSYNTH-8201,CRP,1937-01-05T06:00:00,mg/L,54\n"
                       "SYNTH-8201,CRP,1937-01-06T06:00:00,mg/L,38\n")
    assert r.returncode == 2
    assert r.stderr.splitlines()[0] == "Refused: row 2, column 4 doesn't match the expected layout."
    assert "Refused/LAYOUT" in r.stderr and "SYNTH-8201" not in r.stderr


def test_not_done_in_value_column_is_cross_not_gap(tmp_path):
    r = _run(tmp_path, "patient,local_label,t,value,unit\nSYNTH-8202,CRP,1937-05-02T08:00:00,22,mg/L\n"
                       "SYNTH-8202,CRP,1937-05-03T08:00:00,not done,mg/L\nSYNTH-8202,CRP,1937-05-04T08:00:00,19,mg/L\n")
    assert r.returncode == 0, r.stderr
    leg = (tmp_path / "gallery" / "legends.md").read_text()
    assert "✕ Not done: no test was done at this time." in leg and "couldn't be read" not in leg
    assert "marked as a gap" not in leg and "marked as gaps" not in leg


def test_r10_rows_are_spreadsheet_lines_blank_lines_count(tmp_path):
    # header = row 1; a blank line still counts as a spreadsheet row
    page, leg, r = _gallery(tmp_path, "SYNTH-8121,CRP,1937-10-01 08:00,180,mg/L,final\n\n"
                                      "SYNTH-8121,Synthwidget,1937-10-02 08:00,5,mg/L,final\n"
                                      "SYNTH-8121,CRP,1937-10-03 08:00,90,mg/L,final\n")
    assert "recognise (row 4)." in leg


def test_r10_no_matching_rows_refusal_wording(tmp_path):
    paste = HEAD6 + "SYNTH-8122,Synthwidget,1937-10-02 08:00,5,mg/L,final\nSYNTH-8122,Synthgadget,1937-10-03 08:00,6,mg/L,final\n"
    r = _run(tmp_path, paste)
    assert r.returncode == 2 and r.stdout == ""
    assert r.stderr.splitlines()[0] == "Refused: no rows in the expected layout were found. Nothing was saved."
    assert list(tmp_path.iterdir()) == [tmp_path / "paste.csv"]


@pytest.mark.parametrize("word", ["not done", "missed", "not collected"])
@pytest.mark.parametrize("order", [("patient", "test", "time", "result", "unit"),
                                   ("result", "unit", "time", "test", "patient"),
                                   ("time", "patient", "unit", "result", "test")])
def test_r10_not_done_never_a_gap_any_column_order(tmp_path, word, order):
    rows = [dict(patient="SYNTH-8123", test="CRP", time=f"1937-10-0{d} 08:00", result=v, unit="mg/L")
            for d, v in ((1, "180"), (2, word), (3, "90"))]
    paste = "\t".join(order) + "\n" + "".join("\t".join(r[c] for c in order) + "\n" for r in rows)
    r = _run(tmp_path, paste)
    assert r.returncode == 0, r.stderr
    leg = (tmp_path / "gallery" / "legends.md").read_text()
    assert "0 gap recorded" in leg and "1 gap recorded" not in leg
    assert "Not done" in leg
