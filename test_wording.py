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
