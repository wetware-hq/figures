"""One approved clock (clock.now). Its mode is set explicitly: 'test' gives the scenario clock, 'real' the real clock.
Unset, it refuses with RF-CLOCK-UNSET (pending signing: no text until the row lands) and nothing is saved.
No other code in figures reads the box clock."""
import ast, os, pathlib, re, tempfile
import pytest
import clock
from figures import build

HERE = pathlib.Path(__file__).parent
FIX = (HERE / "fixtures" / "fixture_export.csv").read_text()
BOX = re.compile(r"\b(datetime\.(now|utcnow|today)|date\.today|time\.(time|time_ns|localtime|gmtime|strftime|monotonic|perf_counter))\b")


def _build(tmp):
    d, _ = build(FIX, os.path.join(tmp, "g.html"), as_at="1937-10-16T08:00:00")
    return (pathlib.Path(d) / "legends.md").read_text()


def test_unset_clock_refuses_and_saves_nothing(monkeypatch):
    monkeypatch.delenv("FIGURES_CLOCK", raising=False)
    tmp = tempfile.mkdtemp()
    with pytest.raises(clock.ClockUnset) as e:
        _build(tmp)
    assert e.value.line_id == "RF-CLOCK-UNSET"
    from wording import LINES
    assert e.value.text == LINES.get("RF-CLOCK-UNSET", "")       # unsigned: no text, never invented
    assert os.listdir(tmp) == []


def test_test_mode_gives_the_scenario_clock(monkeypatch):
    monkeypatch.setenv("FIGURES_CLOCK", "test")
    monkeypatch.setenv("FIGURES_SCENARIO_CLOCK", "1937-10-16T08:05:59")
    assert clock.now().isoformat() == "1937-10-16T08:05:59"
    assert "drawn 16 Oct 1937 08:05" in _build(tempfile.mkdtemp())


def test_test_mode_without_a_scenario_time_refuses(monkeypatch):
    monkeypatch.setenv("FIGURES_CLOCK", "test")
    monkeypatch.delenv("FIGURES_SCENARIO_CLOCK", raising=False)
    with pytest.raises(clock.ClockUnset):
        clock.now()


def test_real_mode_figure_never_shows_a_1930s_drawn_date(monkeypatch):
    monkeypatch.setenv("FIGURES_CLOCK", "real")
    monkeypatch.setenv("FIGURES_SCENARIO_CLOCK", "1937-10-16T08:05:00")   # ignored in real mode
    got = re.findall(r"drawn \d\d \w{3} (\d{4})", _build(tempfile.mkdtemp()))
    assert got and not any(y.startswith("193") for y in got)


def test_no_code_outside_clock_py_reads_the_box_clock():
    bad = []
    for p in HERE.rglob("*.py"):
        rel = p.relative_to(HERE).as_posix()
        if rel.startswith((".venv/", "__pycache__")) or rel == "clock.py" or p.name.startswith("test_"):
            continue
        for n, line in enumerate(p.read_text().splitlines(), 1):
            if BOX.search(line.split("#")[0]):
                bad.append(f"{rel}:{n}")
    assert bad == [], bad
