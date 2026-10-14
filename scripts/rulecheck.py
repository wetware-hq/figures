#!/usr/bin/env python3
"""Exit 1 if (a) WORDING.md does not match its header hash, (b) WORDING.md's row count or id set differs from
the current signed file, (c) code calls msg() with an id not in WORDING.md, or (d) figures.py/wording.py hold FG
wording as literals. Exit 0 otherwise."""
import hashlib, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SIGNED = ROOT.parent / "wording" / "forms_orders_lines_SIGNED.md"
ID = r"[A-Z]{2,4}-[A-Z0-9-]+"


def problems():
    out = []
    head, body = (ROOT / "WORDING.md").read_text().split("\n\n", 1)
    if f"sha256: {hashlib.sha256(body.encode()).hexdigest()}" not in head:
        out.append("WORDING.md: content does not match its header hash")
    ours = re.findall(rf"^\| ({ID}) \| [^|]*? \|$", body.split("## Pending signature")[0], re.M)
    signed = re.findall(rf"^\| ({ID}) \|.*\|\s*$", SIGNED.read_text(), re.M)
    if len(ours) != len(signed) or set(ours) != set(signed) or len(set(ours)) != len(ours):
        out.append(f"WORDING.md: {len(ours)} rows vs signed {len(signed)}; ids differ by {sorted(set(ours) ^ set(signed))[:5]}")
    src = "".join((ROOT / f).read_text() for f in ("figures.py", "wording.py"))
    for k in set(re.findall(rf'msg\("({ID})"', src)) - set(ours):
        out.append(f"msg() uses unsigned id {k}")
    lines = dict(re.findall(rf"^\| ({ID}) \| ([^|]*?) \|$", body, re.M))
    for k in ("FG-ROW-OMITTED", "FG-REFUSE-DATA"):
        if k in lines and lines[k].split(" (")[0] in src:
            out.append(f"{k} wording held as a literal in code")
    return out


if __name__ == "__main__":
    p = problems()
    print("\n".join(p) or "rulecheck: OK")
    sys.exit(1 if p else 0)
