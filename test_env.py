from pathlib import Path
from env import Env

REAL = "label\ttime\tresult\tunit\nCRP\t2026-10-01 08:00\t180\tmg/L\n"

def test_clock_settable_on_synthetic_only(tmp_path):
    p = tmp_path / "r.tsv"; p.write_text(REAL)
    assert Env().clean(file=str(p), as_at="2026-10-01T09:00:00")["error"] == "CLOCK_NOT_SETTABLE"
    fx = (Path(__file__).parent / "fixtures/fixture_export.csv").read_text()
    assert Env().clean(text=fx, as_at="2026-10-16T08:00:00")["ok"]

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
