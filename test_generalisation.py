"""Generalisation guard: no hard-coded specialty, ward, discipline or drug name in figures code (.py).
Concepts, units and limits live in concepts.csv / mapping.csv / units.csv / limits.csv."""
import ast, re, tomllib
from pathlib import Path

HERE = Path(__file__).parent
TERMS = tomllib.loads((HERE / "domain_terms.toml").read_text())
RX = {k: re.compile(r"(?<![\w-])(" + "|".join(re.escape(t) for t in v) + r")(?![\w-])", 0 if k == "ward" else re.I)
      for k, v in TERMS.items()}


def scan_file(p):
    tree = ast.parse(Path(p).read_text())
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body and isinstance(n.body[0], ast.Expr)}
    return [(str(p), n.lineno, k, m.group(1)) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs
            for k, rx in RX.items() for m in rx.finditer(n.value)]


def test_figures_code_holds_no_domain_literals():
    files = [p for p in HERE.glob("*.py") if not p.name.startswith("test_")] + list((HERE / "scripts").glob("*.py"))
    hits = [h for p in files if "mutate" not in p.name for h in scan_file(p)]
    assert hits == [], hits


def test_scanner_catches_planted_literal(tmp_path):
    p = tmp_path / "x.py"
    p.write_text('"""about aspirin"""\nX = "warfarin"\nY = "ICU"\nZ = "edit"\n')
    assert {(k, w.lower()) for _, _, k, w in scan_file(p)} == {("drug", "warfarin"), ("ward", "icu")}
