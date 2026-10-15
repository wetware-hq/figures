"""Every figures function that refuses, drops a row or writes a signed line must be listed in safety_functions.toml.
Found by an AST scan, not by hand; a planted omission must fail the check."""
import ast, pathlib, tomllib

ROOT = pathlib.Path(__file__).resolve().parent
CFG = tomllib.loads((ROOT / "safety_functions.toml").read_text())
CALLS = {"msg", "Refused", "layout_refused", "RowsRefused", "DateRefused", "NoRows", "SemicolonPaste"}
PREFIXES = ("FG-", "RF-", "PV-", "CQ-", "REFUSED", "Refused")


def is_safety(f):
    for n in ast.walk(f):
        if isinstance(n, ast.Raise):
            return True
        if isinstance(n, ast.Call) and (getattr(n.func, "id", None) in CALLS or getattr(n.func, "attr", None) in CALLS):
            return True
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith(PREFIXES):
            return True
        if isinstance(n, ast.JoinedStr) and any(isinstance(v, ast.Constant) and str(v.value).startswith(PREFIXES) for v in n.values):
            return True
    return False


def missing(src, listed):
    funcs = [n for n in ast.walk(ast.parse(src)) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return sorted({f.name for f in funcs if is_safety(f)} - listed)


def test_every_safety_function_is_listed():
    for m in CFG["modules"]:
        assert missing((ROOT / m["path"]).read_text(), set(m["functions"])) == [], m["path"]


def test_listed_functions_exist():
    for m in CFG["modules"]:
        names = {n.name for n in ast.walk(ast.parse((ROOT / m["path"]).read_text())) if isinstance(n, ast.FunctionDef)}
        assert set(m["functions"]) <= names, m["path"]


def test_planted_omission_is_caught():
    for m in CFG["modules"]:
        src = (ROOT / m["path"]).read_text()
        scanned = missing(src, set())
        for f in scanned:
            assert missing(src, set(m["functions"]) - {f}) == [f], (m["path"], f)
