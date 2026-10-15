"""Behaviour tests for safety-function branches the first full mutation run left untested."""
import subprocess, types
from pathlib import Path
import polars as pl, pytest
import clean as C, figures as F, env as E

H = "patient\tlabel\ttime\tresult\tunit\tstatus\tsource\n"
FIX = (Path(__file__).parent / "fixtures" / "fixture_export.csv").read_text()
AS_AT = "1937-10-16T08:00:00"


def paste(*rows, head=H, pid="SYNTH-001"):
    return head + "\n".join(f"{pid}\t" + r for r in rows) + "\n"


# ---------- clean.py ----------
def test_empty_paste_refused_as_empty():
    with pytest.raises(C.Refused) as e:
        C.split("  \n\n")
    assert e.value.code == "EMPTY_INPUT"


def test_pipe_header_with_a_time_column_refused():
    text = "patient|label|time|1937-10-01 08:00\nSYNTH-001|CRP|1937-10-01 08:00|5\n"
    with pytest.raises(C.Refused) as e:
        C.clean(text)
    assert e.value.code == "LAYOUT"


def test_missing_required_column_refused_by_name():
    with pytest.raises(C.Refused) as e:
        C.clean("patient\tlabel\ttime\nSYNTH-001\tCRP\t1937-10-01 08:00\n")
    assert e.value.code == "NO_REQUIRED_COLUMN" and "value" in e.value.message


def test_recorded_absence_with_and_without_reason():
    head = "patient\tlabel\ttime\tresult\tunit\tstatus\tgap_reason\n"
    r = C.clean(paste("CRP\t1937-10-01 08:00\t\t\tmissed\t", "CRP\t1937-10-02 08:00\t\t\tmissed\tline tissued",
                      "CRP\t1937-10-03 08:00\t5\tmg/L\tfinal\t", head=head))
    assert r.rows["status"].to_list() == ["absent", "absent", "measured"]
    assert r.rows["gap_reason"].to_list()[:2] == ["recorded absence", "line tissued"]


def test_device_and_specimen_kept_or_null():
    head = "patient\tlabel\ttime\tresult\tunit\tsource\tspecimen\n"
    r = C.clean(paste("CRP\t1937-10-01 08:00\t5\tmg/L\tlab:core\tserum", "CRP\t1937-10-02 08:00\t6\tmg/L\t\t", head=head))
    assert r.rows["device"].to_list() == ["lab:core", None] and r.rows["specimen"].to_list() == ["serum", None]


def test_too_many_series_refused():
    rows = [f"CRP\t1937-10-01 08:{i:02d}\t5\tmg/L\tfinal\tdev{i}" for i in range(C.MAX_SERIES + 1)]
    with pytest.raises(C.Refused) as e:
        C.clean(paste(*rows))
    assert e.value.code == "TOO_MANY_SERIES"
    C.clean(paste(*rows[:C.MAX_SERIES]))                 # exactly the limit is allowed


def test_unit_conversion_picks_the_rows_concept(monkeypatch):
    units = pl.DataFrame({"concept_id": ["sodium", "crp"], "from_unit": ["mg/dL", "mg/dL"], "to_unit": ["x", "mg/L"],
                          "factor": [99.0, 10.0]})
    monkeypatch.setattr(C, "UNITS", units)
    r = C.clean(paste("CRP\t1937-10-01 08:00\t5\tmg/dL\tfinal\tlab"))
    assert r.rows["value"].to_list() == [50.0] and r.rows["unit"].to_list() == ["mg/L"]


def test_clipboard_reads_text_checked_and_allows_real_data(monkeypatch):
    seen = []
    def fake(cmd, **kw):
        seen.append(kw)
        return types.SimpleNamespace(stdout=paste("CRP\t1937-10-01 08:00\t5\tmg/L\tfinal\tlab", pid="REAL-1"))
    monkeypatch.setattr(C.subprocess, "run", fake)
    res = C.from_clipboard()
    assert seen[0] == {"capture_output": True, "text": True, "check": True} and res.synthetic is False


# ---------- env.py ----------
def test_env_stamps_now_when_no_as_at():
    env = E.Env()
    out = env.clean(text=paste("CRP\t1937-10-01 08:00\t5\tmg/L\tfinal\tlab"))
    stored = list(env._h.values())[0][1]
    assert isinstance(stored, str) and stored[:2] in ("19", "20") and "T" in stored


# ---------- figures.py ----------
def test_unmapped_count_counts_label_and_unit_only():
    text = paste("CRP\t1937-10-01 08:00\t5\tmg/L\tfinal\tlab", "Nonsense\t1937-10-01 09:00\t5\tmg/L\tfinal\tlab",
                 "CRP\t1937-10-01 10:00\t5\tfurlongs\tfinal\tlab", "CRP\tnotatime\t5\tmg/L\tfinal\tlab")
    assert F.load(text)[1] == 2


def test_future_absence_is_not_a_future_result(tmp_path):
    text = paste("CRP\t1937-10-01 08:00\t5\tmg/L\tfinal\tlab", "CRP\t1937-10-02 08:00\t6\tmg/L\tfinal\tlab",
                 "CRP\t1937-10-20 08:00\tnot done\t\t\tlab")
    F.build(text, str(tmp_path / "g.html"), as_at=AS_AT)


def test_mapping_version_read_as_text_from_git(monkeypatch, tmp_path):
    vers, real_draw = [], F.draw
    def fake(cmd, **kw):
        assert kw == {"capture_output": True, "text": True}
        return types.SimpleNamespace(stdout=" abc1234\n")
    monkeypatch.setattr(F.subprocess, "run", fake)
    monkeypatch.setattr(F, "draw", lambda *a, **k: (vers.append(a[5]), real_draw(*a, **k))[1])
    F.build(FIX, str(tmp_path / "g.html"), as_at=AS_AT)
    assert vers and set(vers) == {"abc1234"}
    monkeypatch.setattr(F.subprocess, "run", lambda cmd, **kw: types.SimpleNamespace(stdout=""))
    vers.clear(); F.build(FIX, str(tmp_path / "h.html"), as_at=AS_AT)
    assert set(vers) == {"uncommitted"}


def test_cards_in_concept_order(tmp_path):
    text = paste("Lactate\t1937-10-01 08:00\t1.1\tmmol/L\tfinal\tlab", "CRP\t1937-10-01 08:00\t5\tmg/L\tfinal\tlab",
                 "Lactate\t1937-10-02 08:00\t1.2\tmmol/L\tfinal\tlab", "CRP\t1937-10-02 08:00\t6\tmg/L\tfinal\tlab")
    _, checks = F.build(text, str(tmp_path / "g.html"), as_at=AS_AT)
    assert [c[0]["concept_id"][0] for c in checks] == ["crp", "lactate"]


def test_no_range_notice_names_first_row(tmp_path):
    text = paste("CRP\t1937-10-01 08:00\t5\tmg/L\tfinal\tlab", "tumour marker\t1937-10-01 08:00\t30\tU/mL\tfinal\tlab",
                 "tumour marker\t1937-10-02 08:00\t31\tU/mL\tfinal\tlab")
    F.build(text, str(tmp_path / "g.html"), as_at=AS_AT)
    assert F.NO_RANGE_FLAG.format(n=3) in F.NOTICES


def test_unsigned_limits_withhold_interpretation(tmp_path):
    out, _ = F.build(FIX, str(tmp_path / "g.html"), as_at=AS_AT)
    page = (Path(out) / "index.html").read_text()
    import html, wording
    assert html.escape(wording.LINES["FG-INTERP-WITHHELD"]) in page
    assert pl.read_csv(Path(F.__file__).parent / "limits.csv", comment_prefix="#")["status"].to_list().count("SIGNED") == 0


# ---------- unsigned range: value shown, no colour, arrow or flag (FG-INTERP-WITHHELD) ----------
def test_unsigned_synopsis_uses_signed_line_byte_exact(tmp_path):
    import wording, re
    sib = Path(__import__("os").environ.get("WARD_SIBLINGS_DIR") or Path(F.__file__).parent.parent)
    raw = (sib / "wording" / "forms_orders_lines_SIGNED.md").read_bytes().decode("utf-8")
    want = re.search(r"^\| FG-INTERP-WITHHELD \| (.*) \|$", raw, re.M).group(1)
    out, checks = F.build(FIX, str(tmp_path / "g.html"), as_at=AS_AT)
    assert want in (Path(out) / "legends.md").read_text()
    assert all(F.interp_marks(fig, s) == [] for s, _, fig in checks)
    assert all(s.filter(pl.col("status") == "measured").height for s, _, _ in checks)    # values still shown


@pytest.mark.parametrize("tamper", ["colour", "arrow_marker", "annotation"])
def test_any_marker_on_unsigned_value_refused(tmp_path, monkeypatch, tamper):
    real = F.draw
    def marked(s, *a, **k):
        fig, runs, meas = real(s, *a, **k)
        ax, p = fig.axes[0], s.filter(pl.col("status") == "measured").row(0, named=True)
        if tamper == "colour":
            ax.plot([p["t"]], [p["v"]], marker="o", color="red", ls="none")
        elif tamper == "arrow_marker":
            ax.plot([p["t"]], [p["v"]], marker="^", color="C0", ls="none")
        else:
            ax.annotate("high", (p["t"], p["v"]), xytext=(5, 5), textcoords="offset points", arrowprops=dict(arrowstyle="->"))
        return fig, runs, meas
    monkeypatch.setattr(F, "draw", marked)
    with pytest.raises(SystemExit, match="normal range isn't signed off"):
        F.build(FIX, str(tmp_path / "g.html"), as_at=AS_AT)


# ---------- signed-limits path of synopsis (no SIGNED rows on file yet; exercised with test rows) ----------
from datetime import datetime as _dt


def _runs(v0, vl, concept="crp"):
    return [[{"v": v0, "t": _dt(1937, 10, 1, 8), "concept_id": concept}, {"v": vl, "t": _dt(1937, 10, 3, 8), "concept_id": concept}]]


def _syn(v0, vl, **row):
    return F.synopsis(None, _runs(v0, vl), dict(status="SIGNED", **row), "mg/L")


def test_synopsis_signed_trend_words_follow_thresholds():
    assert "Fell at about the expected rate" in _syn(100, 50, expected_half_life_h=19)
    assert "Changed within test noise" in _syn(50, 100, expected_half_life_h=19)
    assert " Fell " in _syn(100, 80, rcv_fall_pct=20) and " Fell " in _syn(100, 75, rcv_fall_pct=20)
    assert "Changed" in _syn(100, 90, rcv_fall_pct=20) and "Changed" in _syn(100, 150, rcv_fall_pct=20)
    assert " Rose " in _syn(100, 120, rcv_rise_pct=20) and "Changed" in _syn(100, 110, rcv_rise_pct=20)
    assert "Changed" in _syn(100, 50, rcv_rise_pct=20)
    assert "Changed" in _syn(100, 90)


def test_synopsis_drops_numbers_then_kinetics_to_fit(monkeypatch):
    full = _syn(100, 50, expected_half_life_h=19)
    assert "100 to 50 mg/L" in full and len(full) <= F.MAX_LINE1
    monkeypatch.setattr(F, "MAX_LINE1", len(full) - 1)
    mid = _syn(100, 50, expected_half_life_h=19)
    assert "100 to 50" not in mid and "expected rate" in mid
    monkeypatch.setattr(F, "MAX_LINE1", 10)
    assert _syn(100, 50, expected_half_life_h=19) == "Read with the bedside. Fell; possible reasons need the clinical picture."


def test_unsigned_footer_says_interpretation_withheld(tmp_path):
    _, checks = F.build(FIX, str(tmp_path / "g.html"), as_at=AS_AT)
    assert all(any("Interpretation withheld" in t.get_text() for t in fig.texts) for _, _, fig in checks)


def test_empty_value_without_absent_status_is_rejected_not_an_absence():
    r = C.clean(paste("CRP\t1937-10-01 08:00\t\t\tfinal\tlab", "CRP\t1937-10-02 08:00\t5\tmg/L\tfinal\tlab"))
    assert r.rows["status"].to_list() == ["measured"] and any(f == "value" for _, f, _ in r.rejects)
