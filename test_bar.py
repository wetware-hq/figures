"""BAR guard: every jurisdiction-scan category the scan runs under MUST be listed in BAR.md.
A check cannot run under a name the bar does not name."""
import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent
CFG = tomllib.loads((ROOT / "jurisdiction_scan.toml").read_text())
BAR = (ROOT / "BAR.md").read_text()


def test_every_scan_category_is_listed_in_bar():
    missing = sorted(c for c in CFG["categories"] if c not in BAR)
    assert not missing, f"scan categories not listed in BAR.md: {missing}"
