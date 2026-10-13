"""Formal agent environment over clean.py + figures.py.
Episode = one session. Actions: clean, rejects, render, close. Every observation validates against schemas/.
Zero retention: handles live in memory for the session only. Clock: settable on synthetic data only."""
import json, secrets
from datetime import datetime
from pathlib import Path
import jsonschema
from clean import clean, from_file, from_clipboard, Refused

HERE = Path(__file__).parent
SCHEMAS = {p.stem: json.loads(p.read_text()) for p in (HERE / "schemas").glob("*.json")}
ERRORS = ["EMPTY_INPUT", "NO_REQUIRED_COLUMN", "NOT_PROVABLY_SYNTHETIC", "MULTIPLE_PATIENTS", "TOO_MANY_SERIES",
          "INTERLEAVED_TIME", "MIXED_TIME_ORDER", "NO_CLIPBOARD", "REAL_DATA_NOT_WRITTEN", "UNKNOWN_HANDLE",
          "CLOCK_NOT_SETTABLE", "REAL_RENDER_LOCAL_DISPLAY_ONLY", "BAD_ACTION"]

def _ok(kind, obs):
    jsonschema.validate(obs, SCHEMAS[kind]); return obs

def _err(code, message):
    assert code in ERRORS
    return _ok("error", {"ok": False, "error": code, "message": message})

class Env:
    def __init__(self):
        self._h = {}

    def clean(self, text=None, file=None, clipboard=False, as_at=None):
        try:
            res = from_clipboard() if clipboard else from_file(file) if file else clean(text or "")
        except Refused as e:
            return _err(e.code, e.message)
        if as_at is not None and not res.synthetic:
            return _err("CLOCK_NOT_SETTABLE", "Refused: the as-at time comes from this machine's clock on real data.")
        h = secrets.token_hex(4)
        self._h[h] = (res, as_at or datetime.now().replace(microsecond=0).isoformat())
        return _ok("clean", {"ok": True, "handle": h, **res.summary()})

    def rejects(self, handle):
        if handle not in self._h:
            return _err("UNKNOWN_HANDLE", "No such handle in this session.")
        return _ok("rejects", {"ok": True, "rejects": [{"line": l, "field": f, "reason": r} for l, f, r in self._h[handle][0].rejects]})

    def render(self, handle, out="gallery"):
        if handle not in self._h:
            return _err("UNKNOWN_HANDLE", "No such handle in this session.")
        res, as_at = self._h[handle]
        if not res.synthetic:
            return _err("REAL_RENDER_LOCAL_DISPLAY_ONLY", "Real data is drawn on the ward machine's screen only; nothing is returned or written.")
        import figures
        pid = "SYNTH-001"
        rows = ["patient,local_label,t,value,unit,device,derivation,status,gap_reason"]
        for r in res.rows.filter(res.rows["status"] != "censored").iter_rows(named=True):
            v = "" if r["value"] is None else r["value"]
            rows.append(f'{pid},{r["local_label"]},{r["t"]:%Y-%m-%dT%H:%M:%S},{v},{r["unit"]},{r["device"] or "unknown"},assay,'
                        f'{"measured" if r["status"] == "measured" else "absent"},{r["gap_reason"] or ""}')
        figures.build("\n".join(rows), out + ".html", as_at=as_at)
        files = sorted(str(p) for p in Path(out).glob("*"))
        return _ok("render", {"ok": True, "shown": True, "files": files})

    def close(self):
        self._h.clear(); return {"ok": True}

    def step(self, action, **kw):
        if action not in ("clean", "rejects", "render", "close"):
            return _err("BAD_ACTION", f"Unknown action {action!r}.")
        return getattr(self, action)(**kw)
