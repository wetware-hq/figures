"""Loads user-facing lines from WORDING.md (synced from the signed table by scripts/sync_wording.py); no wording here."""
import pathlib, re

WORDING = pathlib.Path(__file__).resolve().parent / "WORDING.md"
_TEXT = WORDING.read_text()
_BODY = _TEXT.split("\n\n", 1)[1]
SHA256 = re.search(r"^sha256: ([0-9a-f]{64})$", _TEXT, re.M).group(1)
LINES = dict(re.findall(r"^\| ([A-Z]{2,4}-[A-Z0-9-]+) \| ([^|]*?) \|$", _BODY, re.M))


def msg(line_id, event_id):
    """A signed line with its [event_id] slot filled."""
    return LINES[line_id].replace("[event_id]", str(event_id))
