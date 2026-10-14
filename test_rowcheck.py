"""Row data check inside figures (safety): bad rows dropped with FG-ROW-OMITTED in the caption; none left -> FG-REFUSE-DATA, no figure."""
import re
from pathlib import Path
import pytest
import figures
from figures import build, main, row_check, row_fault, RowsRefused
from wording import msg

HEAD = "patient,local_label,t,value,unit,device,derivation,status,gap_reason,event_id"
AS_AT = "1937-10-20T08:00:00"
def row(t="1937-10-14T08:00:00", v="12", u="mg/L", st="measured", ev="SYNTH-EP-1#1"):
    return f"SYNTH-001,CRP,{t},{v},{u},lab:core,assay,{st},,{ev}"
GOOD = [row(t=f"1937-10-1{i}T08:00:00", v=str(10 + i), ev=f"SYNTH-EP-1#{i}") for i in (1, 2, 3)]
REC1005 = row(t="1937-10-15T08:00:00", v="40", u="", ev="SYNTH-EP-1#7")      # SYNTH-REC-1005: CRP with no unit

def paste(*rows): return "\n".join([HEAD, *rows]) + "\n"

def test_synth_rec_1005_direct_no_stack(tmp_path):
    d, checks = build(paste(*GOOD, REC1005), str(tmp_path / "g.html"), as_at=AS_AT)
    cap = (Path(d) / "legends.md").read_text()
    want = "Result not shown: it failed a data check (event SYNTH-EP-1#7)."
    assert cap.count(want) == 1 and "Figure not made" not in cap
    assert sum(len(r) for _, runs, _ in checks for r in runs) == 3                  # exactly 3 plotted points
    assert f"<p class=omitted>{want}</p>" in (Path(d) / "index.html").read_text()

def test_each_bad_row_once_in_order(tmp_path):
    bad = [row(u="", ev="E#a"), row(v="x", ev="E#b"), row(t="14/10/1937", ev="E#c"), row(t="1937-02-30T08:00:00", ev="E#d")]
    d, _ = build(paste(GOOD[0], bad[0], GOOD[1], bad[1], bad[2], bad[3]), str(tmp_path / "g.html"), as_at=AS_AT)
    cap = (Path(d) / "legends.md").read_text()
    lines = [msg("FG-ROW-OMITTED", e) for e in ("E#a", "E#b", "E#c", "E#d")]
    assert [cap.count(l) for l in lines] == [1, 1, 1, 1]
    assert [cap.index(l) for l in lines] == sorted(cap.index(l) for l in lines)

def test_all_bad_no_figure_refuse_line(tmp_path, monkeypatch, capsys):
    with pytest.raises(RowsRefused) as e:
        build(paste(REC1005, row(v="", ev="E#2")), str(tmp_path / "g.html"), as_at=AS_AT)
    assert e.value.lines == [msg("FG-REFUSE-DATA", "SYNTH-EP-1#7"), msg("FG-REFUSE-DATA", "E#2")]
    assert not (tmp_path / "g").exists()
    monkeypatch.chdir(tmp_path); (tmp_path / "in.csv").write_text(paste(REC1005))
    assert main(["in.csv", f"--as-at={AS_AT}"]) == 2
    err = capsys.readouterr().err
    assert msg("FG-REFUSE-DATA", "SYNTH-EP-1#7") in err and "Result not shown" not in err
    assert not (tmp_path / "gallery").exists()

def test_all_good_caption_has_no_fg_lines(tmp_path):
    d, _ = build(paste(*GOOD), str(tmp_path / "g.html"), as_at=AS_AT)
    cap = (Path(d) / "legends.md").read_text()
    assert "data check" not in cap and "Figure not made" not in cap
    assert "class=omitted" not in (Path(d) / "index.html").read_text()

def test_no_event_id_column_is_unchanged():
    t = "patient,local_label,t,value,unit\nSYNTH-001,CRP,1937-10-14T08:00:00,1,\n"
    assert row_check(t) == (t, [], [])

def test_missing_event_id_cell_uses_row_number():
    _, lines, ids = row_check(paste(GOOD[0], row(u="", ev="")))
    assert ids == ["row 3"] and lines == [msg("FG-ROW-OMITTED", "row 3")]

@pytest.mark.parametrize("r,why", [
    (dict(t="1937-10-14T08:00:00", value="1", unit="mg/L", status="measured"), None),
    (dict(t="1937-10-14T08:00", value="1", unit="mg/L"), None),
    (dict(t="1937-10-14T08:00:00", value="1", unit="mg/L"), None),
    (dict(t=" 1937-10-14T08:00:00 ", value=" 1.5 ", unit=" mg/L ", status=" measured "), None),
    (dict(t="1937-10-14", value="1", unit="mg/L"), "time"),
    (dict(t="1937-10-14T08:00:00.500", value="1", unit="mg/L"), "time"),
    (dict(t="1937-10-14T08:00:00", value="1", unit="", status=" measured "), "unit"),
    (dict(t="x1937-10-14T08:00:00", value="1", unit="mg/L"), "time"),
    (dict(t="1937-10-14T08:00:00x", value="1", unit="mg/L"), "time"),
    (dict(t="1937-13-14T08:00:00", value="1", unit="mg/L"), "time"),
    (dict(t=None, value="1", unit="mg/L"), "time"),
    (dict(t="1937-10-14T08:00:00", value="1", unit=""), "unit"),
    (dict(t="1937-10-14T08:00:00", value="1", unit="  "), "unit"),
    (dict(t="1937-10-14T08:00:00", value="1", unit=None), "unit"),
    (dict(t="1937-10-14T08:00:00", value="", unit="mg/L"), "value"),
    (dict(t="1937-10-14T08:00:00", value=None, unit="mg/L"), "value"),
    (dict(t="1937-10-14T08:00:00", value="n/a", unit="mg/L"), "value"),
    (dict(t="1937-10-14T08:00:00", value="", unit="", status="absent"), None),
    (dict(t="1937-10-14T08:00:00", value="", unit="", status=None), "unit"),
    (dict(t="", value="", unit="", status="absent"), "time"),
])
def test_row_fault_table(r, why):
    assert row_fault(r) == why


def test_header_only_paste_is_not_a_refusal():
    assert row_check(HEAD + "\n") == (HEAD + "\n", [], [])
