"""Regression tests (not a held-out evaluation). Each case: clean (twice, for determinism), check the expected outcome,
and for renders check the wording rules. Exit 1 on any failure. Tier 2 (people) is READER_TEST.md."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from env import Env

ROOT = Path(__file__).parents[1]
DIRECTION = re.compile(r"\b(fell|rose|fall|rise|improv\w*|worsen\w*|deteriorat\w*|declin\w*|increas\w*|decreas\w*|went from)\b", re.I)

def strip(o):
    o = dict(o); o.pop("handle", None); return o

def run_case(name, c):
    env = Env()
    text = (ROOT / "fixtures/fixture_export.csv").read_text() if c.get("fixture") else c["text"]
    a, b = env.clean(text=text, as_at=c.get("as_at")), Env().clean(text=text, as_at=c.get("as_at"))
    fails = [] if strip(a) == strip(b) else ["not deterministic"]
    e = c["expect"]
    if "error" in e and a.get("error") != e["error"]:
        fails.append(f"expected {e['error']}, got {a.get('error') or 'ok'}")
    if e.get("ok") and not a.get("ok"):
        fails.append(f"expected ok, got {a.get('error')}")
    if "n" in e and a.get("ok") and sum(s["n"] for s in a["series"]) != e["n"]:
        fails.append(f"expected {e['n']} rows")
    if "reject" in e and e["reject"] not in a.get("rejects", {}):
        fails.append(f"missing reject {e['reject']}")
    if c.get("render") and a.get("ok"):
        r = env.render(a["handle"], out=f"/tmp/eval_{name}")
        legends = Path(f"/tmp/eval_{name}/legends.md").read_text()
        if "withheld" in legends and DIRECTION.search(legends.split("*For the clinical team:*")[0]):
            fails.append("withheld legend uses a direction word")
        svg = Path(f"/tmp/eval_{name}/figure_1.svg").read_text()
        if "identity not verified" not in svg and a["identity"] != "verified":
            fails.append("footer claims identity without an ID match")
    return fails

if __name__ == "__main__":
    bad = 0
    for p in sorted((ROOT / "evals/cases").glob("*.json")):
        f = run_case(p.stem, json.loads(p.read_text()))
        bad += bool(f); print(("PASS " if not f else "FAIL ") + p.stem + ("" if not f else ": " + "; ".join(f)))
    print(f"regression tests: {bad} failed"); sys.exit(1 if bad else 0)
