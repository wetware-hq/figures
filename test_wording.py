import pytest
import hashlib, re
from pathlib import Path
import wording
TEXT = (Path(__file__).parent / "WORDING.md").read_text()

def test_wording_matches_its_header_hash():
    head, body = TEXT.split("\n\n", 1)
    assert re.search(r"^sha256: ([0-9a-f]{64})$", head, re.M).group(1) == hashlib.sha256(body.encode()).hexdigest()
    assert wording.SHA256 == hashlib.sha256(body.encode()).hexdigest()

def test_any_edit_breaks_the_hash():
    head, body = TEXT.split("\n\n", 1)
    assert hashlib.sha256(body.replace("data check", "data chek", 1).encode()).hexdigest() != wording.SHA256

def test_only_ids_and_wording():
    body = TEXT.split("\n\n", 1)[1].splitlines()
    assert body[:2] == ["| id | line |", "|---|---|"]
    assert all(re.fullmatch(r"\| [A-Z]{2,4}-[A-Z0-9-]+ \| [^|]*? \|", l) for l in body[2:] if l)

def test_fg_lines_are_the_signed_ones():
    assert wording.LINES["FG-ROW-OMITTED"] == "Result not shown: it failed a data check (event [event_id])."
    assert wording.LINES["FG-REFUSE-DATA"] == "Figure not made: the data failed a check (event [event_id])."
    assert wording.msg("FG-ROW-OMITTED", "E#3").endswith("(event E#3).")

def test_figures_holds_no_fg_wording():
    src = (Path(__file__).parent / "figures.py").read_text() + (Path(__file__).parent / "wording.py").read_text()
    assert "failed a data check" not in src and "Figure not made" not in src


def _sync():
    import importlib.util
    spec = importlib.util.spec_from_file_location("sync_wording", Path(__file__).parent / "scripts" / "sync_wording.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

SIGNED = "| id | line |\n|---|---|\n| PV-OPEN | Not answered yet |\n| LT-X | clinician | x | Three-column row. |\n"

def test_sync_keeps_every_signed_row_including_multi_column():
    sw = _sync()
    out = sw.render(SIGNED)
    assert "| LT-X | Three-column row. |" in out and "| PV-OPEN | Not answered yet |" in out

@pytest.mark.parametrize("cut", ["drop_row", "rename_id", "duplicate"])
def test_sync_refuses_row_count_or_id_mismatch(cut):
    sw = _sync()
    body = sw.body(SIGNED)
    bad = {"drop_row": body.replace("| PV-OPEN | Not answered yet |\n", ""),
           "rename_id": body.replace("| PV-OPEN |", "| PV-OPN |"),
           "duplicate": body.replace("| LT-X | Three-column row. |\n", "| PV-OPEN | Not answered yet |\n")}[cut]
    with pytest.raises(SystemExit):
        sw.verify(SIGNED, bad)

SIGNED_FILE = Path(__import__("os").environ.get("STACK_SIBLINGS_DIR") or Path(__file__).parent.parent) / "wording" / "forms_orders_lines_SIGNED.md"


def test_wording_md_equals_current_signed_file():
    """Signed rule: WORDING.md has exactly the signed file's row count and id set, read now; no hard-coded count."""
    signed = re.findall(r"^\| ([A-Z]{2,4}-[A-Z0-9-]+) \|.*\|\s*$", SIGNED_FILE.read_text(), re.M)
    body = TEXT.split("\n\n", 1)[1].split("## Pending signature")[0]
    ours = re.findall(r"^\| ([A-Z]{2,4}-[A-Z0-9-]+) \| [^|]*? \|$", body, re.M)
    assert signed, "signed file has no rows"
    assert len(ours) == len(signed), f"WORDING.md has {len(ours)} rows, signed file has {len(signed)}"
    assert set(ours) == set(signed), sorted(set(ours) ^ set(signed))
    assert len(set(ours)) == len(ours), "duplicate id in WORDING.md"
    _sync().verify(SIGNED_FILE.read_text(), TEXT.split("\n\n", 1)[1])