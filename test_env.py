from pathlib import Path
from env import Env

REAL = "label\ttime\tresult\tunit\nCRP\t1937-10-01 08:00\t180\tmg/L\n"

def test_clock_settable_on_synthetic_only(tmp_path):
    p = tmp_path / "r.tsv"; p.write_text(REAL)
    assert Env().clean(file=str(p), as_at="1937-10-01T09:00:00")["error"] == "CLOCK_NOT_SETTABLE"
    fx = (Path(__file__).parent / "fixtures/fixture_export.csv").read_text()
    assert Env().clean(text=fx, as_at="1937-10-16T08:00:00")["ok"]

def test_real_render_returns_nothing_and_writes_nothing(tmp_path):
    p = tmp_path / "r.tsv"; p.write_text(REAL)
    e = Env(); h = e.clean(file=str(p))["handle"]
    r = e.render(h, out=str(tmp_path / "g"))
    assert r["error"] == "REAL_RENDER_LOCAL_DISPLAY_ONLY" and not (tmp_path / "g").exists()

def test_handles_die_with_session():
    fx = (Path(__file__).parent / "fixtures/fixture_export.csv").read_text()
    e = Env(); h = e.clean(text=fx)["handle"]; e.close()
    assert e.rejects(h)["error"] == "UNKNOWN_HANDLE"
    assert Env().rejects(h)["error"] == "UNKNOWN_HANDLE"

def test_unknown_action_is_typed_error():
    assert Env().step("drop_table")["error"] == "BAD_ACTION"



def test_r11f_render_uses_the_pastes_own_patient_id(tmp_path, monkeypatch):
    import figures
    seen = []
    monkeypatch.setattr(figures, "build", lambda text, *a, **k: seen.append(text) or (str(tmp_path), []))
    from env import Env
    e = Env()
    h = e.clean("patient\tlabel\tunit\t1937-10-01 08:00\t1937-10-02 08:00\nSYNTH-4242\tCRP\tmg/L\t180\t140")["handle"]
    e.render(h, out=str(tmp_path / "g"))
    assert "SYNTH-4242" in seen[0] and "SYNTH-001" not in seen[0]



def test_r11g_render_keeps_censored_rows_as_limit_markers(tmp_path, monkeypatch):
    import figures
    from clean import clean
    seen = []
    monkeypatch.setattr(figures, "build", lambda text, *a, **k: seen.append(text) or (str(tmp_path), []))
    paste = ("patient\tlabel\tunit\t1937-10-01 08:00\t1937-10-02 08:00\t1937-10-03 08:00\t1937-10-04 08:00\n"
             "SYNTH-4242\tCRP\tmg/L\t180\t<5\t140\t>300")
    e = Env(); h = e.clean(paste)["handle"]
    e.render(h, out=str(tmp_path / "g"))
    rows = clean(seen[0]).rows.sort("t")                          # what the main path parses: nothing dropped
    assert rows.height == 4 and rows["status"].to_list() == ["measured", "censored", "measured", "censored"]
    assert rows["bound"].to_list()[1::2] == ["<", ">"] and rows["value"].to_list()[1::2] == [5.0, 300.0]
    direct = clean(paste).rows.sort("t")
    assert rows.select("t", "value", "status", "bound").equals(direct.select("t", "value", "status", "bound"))


def test_r11g_render_draws_censored_markers_and_legend(tmp_path):
    paste = ("patient\tlabel\tunit\t1937-10-01 08:00\t1937-10-02 08:00\t1937-10-03 08:00\n"
             "SYNTH-4242\tCRP\tmg/L\t180\t<5\t140")
    e = Env(); h = e.clean(paste)["handle"]
    r = e.render(h, out=str(tmp_path / "g"))
    assert r["ok"]
    html = "".join(Path(f).read_text(errors="replace") for f in r["files"] if f.endswith((".html", ".svg", ".txt", ".md")))
    assert "▼" in html and "below the test's limit (<5" in html
