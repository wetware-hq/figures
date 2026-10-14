#!/usr/bin/env python3
"""Mutation run for the row data check (a safety check): every mutant must be killed by test_rowcheck.py/test_wording.py.
No exclusions. Each mutant edits a copy of the repo, never the repo itself."""
import pathlib, shutil, subprocess, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv" / "bin" / "python")
MUTANTS = [
    ("figures.py", '    if not ISO_T.fullmatch(t):\n        return "time"', '    if False:\n        return "time"'),
    ("figures.py", 'ISO_T.fullmatch(t)', 'ISO_T.match(t)'),
    ("figures.py", '(:\\d{2})?")', '(:\\d{2})")'),
    ("figures.py", '        datetime.fromisoformat(t)\n', '        pass\n'),
    ("figures.py", '    if (row.get("status") or "measured").strip() != "measured":\n        return None', '    if False:\n        return None'),
    ("figures.py", '(row.get("status") or "measured")', '(row.get("status") or "absent")'),
    ("figures.py", '(row.get("status") or "measured").strip()', '(row.get("status") or "measured")'),
    ("figures.py", '    if not (row.get("unit") or "").strip():\n        return "unit"', '    if False:\n        return "unit"'),
    ("figures.py", '(row.get("unit") or "").strip()', '(row.get("unit") or "")'),
    ("figures.py", '        float((row.get("value") or "").strip())', '        pass'),
    ("figures.py", '    t = (row.get("t") or "").strip()', '    t = (row.get("t") or "")'),
    ("figures.py", '        if row_fault(row):', '        if False:'),
    ("figures.py", '            keep.append(raw)', '            pass'),
    ("figures.py", 'or f"row {n}")', 'or "row")'),
    ("figures.py", 'start=2):', 'start=1):'),
    ("figures.py", '    if len(keep) == 1 and ids:', '    if False:'),
    ("figures.py", '    if len(keep) == 1 and ids:', '    if len(keep) == 1:'),
    ("figures.py", '[msg("FG-REFUSE-DATA", i) for i in ids]', '[msg("FG-ROW-OMITTED", i) for i in ids]'),
    ("figures.py", '[msg("FG-ROW-OMITTED", i) for i in ids], ids', '[msg("FG-REFUSE-DATA", i) for i in ids], ids'),
    ("figures.py", '[msg("FG-ROW-OMITTED", i) for i in ids], ids', '[msg("FG-ROW-OMITTED", i) for i in ids[:1]], ids'),
    ("figures.py", '    text, omitted, _ = row_check(text)', '    omitted = row_check(text)[1]'),
    ("figures.py", '+ "".join(f"\\n{x}\\n" for x in omitted))', ')'),
    ("figures.py", '+ "".join(f"<p class=omitted>{html.escape(x)}</p>" for x in omitted))', ')'),
    ("figures.py", '        if isinstance(e, RowsRefused):\n            msg = str(e)', '        if False:\n            msg = str(e)'),
    ("figures.py", '    if "event_id" not in (text.splitlines() or [""])[0].split(","):\n        return text, [], []', '    if False:\n        return text, [], []'),
    ("wording.py", 'return LINES[line_id].replace("[event_id]", str(event_id))', 'return LINES[line_id]'),
    ("WORDING.md", "failed a data check", "failed a data chek"),
]

def main():
    alive = []
    for i, (f, a, b) in enumerate(MUTANTS):
        with tempfile.TemporaryDirectory() as d:
            dst = pathlib.Path(d) / "figures"
            shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".venv", ".git", "__pycache__", "gallery", "g*.png"))
            src = (dst / f).read_text()
            if a not in src:
                print(f"mutant {i}: NOT FOUND {f}: {a!r}"); alive.append(i); continue
            (dst / f).write_text(src.replace(a, b, 1))
            r = subprocess.run([PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "test_rowcheck.py", "test_wording.py"],
                               cwd=dst, capture_output=True, text=True)
            ok = r.returncode != 0
            print(f"mutant {i}: {'killed' if ok else 'SURVIVED'}  {f}: {a.strip()[:60]}")
            if not ok: alive.append(i)
    print(f"{len(MUTANTS) - len(alive)} of {len(MUTANTS)} mutants killed")
    return 1 if alive else 0

if __name__ == "__main__":
    sys.exit(main())
