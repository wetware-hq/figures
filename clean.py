"""Zero-retention local processing for messy EMR flowsheet pastes.
Nothing leaves and nothing is kept. Text input is accepted only when provably synthetic;
real data enters from a local file or the clipboard, and agents receive counts only."""
import csv, io, re, sys, json, subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import polars as pl

HERE = Path(__file__).parent
MAP = pl.read_csv(HERE / "mapping.csv")
UNITS = pl.read_csv(HERE / "units.csv")
SYNTH = re.compile(r"^SYNTH-\d+$")
ALIASES = {
    "patient": ["patient", "mrn", "urn", "patient id", "id"],
    "local_label": ["local_label", "label", "test", "item", "observation", "name"],
    "t": ["t", "time", "date", "datetime", "collected", "date/time"],
    "value": ["value", "result", "val"],
    "unit": ["unit", "units", "uom"],
    "status": ["status", "result status"],
    "device": ["device", "source", "analyser", "method"],
    "specimen": ["specimen", "sample"],
    "gap_reason": ["gap_reason", "gap reason"],
    "as_at": ["as_at", "as at"],
}
NOT_DONE_WORDS = {"not done", "missed", "not collected"}
ABSENT_STATUS = {"absent", "missed", "not done", "not collected"}
COMMENTS = {"haemolysed": "haemolysed", "hemolysed": "haemolysed", "hemolyzed": "haemolysed",
            "insufficient": "insufficient sample", "cancelled": "cancelled", "canceled": "cancelled",
            "see comment": "see comment", "to follow": "result to follow", "pending": "result to follow",
            "clotted": "clotted"}
NUM = r"[-+]?\d+(?:\.\d+)?"

class Refused(SystemExit):
    """A refusal with a stable machine code; the message is for people. row/col point at the cell (no text)."""
    def __init__(self, code, message, row=None, col=None):
        super().__init__(message); self.code, self.message, self.row, self.col = code, message, row, col
    def __str__(self):
        return self.message

MAX_SERIES = 50

TRIPWIRE = ("Refused: this looks like real patient data. It has already been copied into this chat, "
            "so treat it as a privacy incident. Don't paste it again or anywhere else. Report it to your "
            "organisation's privacy officer through your usual incident process, noting the time and where it was "
            "pasted. For real data, use the ward computer's file or clipboard path.")

@dataclass
class Result:
    rows: pl.DataFrame
    rejects: list = field(default_factory=list)   # (line, field, reason) only, never the raw line
    synthetic: bool = False
    identity_verified: bool = False
    order: str = "oldest-first"
    unreadable: list = field(default_factory=list)  # (concept_id, time) of rows dropped after a readable time; no text
    no_time: int = 0                                # rows dropped because the time could not be read

    def summary(self):
        """What an agent may see. Real data: counts, units and reject reasons only."""
        reasons = {}
        for _, f, r in self.rejects:
            reasons[f"{f}: {r}"] = reasons.get(f"{f}: {r}", 0) + 1
        out = {"synthetic": self.synthetic, "identity": "verified" if self.identity_verified else "not verified",
               "rejects": reasons,
               "series": [{"concept": c, "unit": u, "n": n} for c, u, n in
                          self.rows.group_by(["concept_id", "unit"]).len().sort("concept_id").iter_rows()]}
        if self.synthetic:
            out["rows"] = self.rows.with_columns(pl.col("t").dt.strftime("%Y-%m-%dT%H:%M")).to_dicts()
        return out

# ---------- reading ----------
def split(text):
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        raise Refused("EMPTY_INPUT", "Refused: empty input.")
    sample = "\n".join(lines[:20])
    for d in ["\t", "|", ","]:
        if all(d in l for l in lines[:5]):
            return [[c.strip() for c in r] for r in csv.reader(io.StringIO("\n".join(lines)), delimiter=d)]
    return [re.split(r"\s{2,}", l.strip()) for l in lines]

def header_map(head):
    m = {}
    for i, h in enumerate(head):
        k = h.strip().lower()
        for canon, names in ALIASES.items():
            if k in names and canon not in m:
                m[canon] = i
    return m

def parse_time(s):
    s = s.strip()
    for f in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f), None
        except ValueError:
            pass
    m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})(?:[ T](\d{1,2}):(\d{2}))?$", s)
    if m:
        a, b = int(m[1]), int(m[2])
        if a <= 12 and b <= 12 and a != b:
            return None, "ambiguous day/month order"
        d, mo = (a, b) if a > 12 or a == b else (b, a) if b > 12 else (a, b)
        y = int(m[3]); y = y + 2000 if y < 100 else y
        try:
            return datetime(y, mo, d, int(m[4] or 0), int(m[5] or 0)), None
        except ValueError:
            return None, "impossible date"
    return None, "unreadable time"

def parse_value(s):
    """-> (value, status, bound_or_reason). Flags are stripped; reference ranges are never taken as the result."""
    raw = s.strip()
    low = raw.lower()
    for k, reason in COMMENTS.items():
        if k in low:
            return None, "absent", reason
    v = re.sub(r"\(\s*" + NUM + r"\s*[-–]\s*" + NUM + r"\s*\)", "", raw)      # pasted reference range
    v = re.sub(r"\[\s*" + NUM + r"\s*[-–]\s*" + NUM + r"\s*\]", "", v)
    v = re.sub(r"(?<=\d)\s*(HH|LL|H|L|\*+|!|A|C)\s*$", "", v.strip()).strip()   # trailing flag
    v = re.sub(r"^\*+\s*", "", v)
    if re.fullmatch(NUM + r"\s*[-–]\s*" + NUM, v):
        return None, "reject", "looks like a reference range, not a result"
    m = re.fullmatch(r"([<>]=?)\s*(" + NUM + ")", v)
    if m:
        return float(m[2]), "censored", m[1]
    if re.fullmatch(NUM, v):
        return float(v), "measured", None
    return None, "reject", "not a number, a censored value or a known lab comment"

# ---------- cleaning ----------
def file_lines(text):
    """Spreadsheet-style row numbers: the file's own line numbers, header = row 1 (blank lines still count)."""
    return [n for n, l in enumerate(text.splitlines(), 1) if l.strip()]

def known(cell):
    k = cell.strip().lower()
    return next((canon for canon, names in ALIASES.items() if k in names), None)

def layout_refused(row, col):
    where = f"row {row or 1}, column {col}"
    return Refused("LAYOUT", f"Refused: {where} doesn't match the expected layout.", row, col)

def strict_header(head, wide=False):
    """Pipe and wide pastes: every column must match one known header, unambiguously (wide: or be a time)."""
    seen = {}
    for j, cell in enumerate(head, 1):
        canon = known(cell)
        if canon is None and not (wide and parse_time(cell)[0] is not None):
            raise layout_refused(None, j)
        if canon is not None:
            if canon in seen:
                raise layout_refused(None, j)
            seen[canon] = j

def swapped_columns(h, body, rows_at=None):
    """Catch swapped columns, naming row and column: time and value swapped (a number in the time column, a time in
    the value column), or value and unit swapped (no digit in the value column, a plain number in the unit column)."""
    cell = lambda r, k: r[h[k]].strip() if k in h and h[k] < len(r) else ""
    for k, r in enumerate(body, 2):
        n = rows_at[k - 1] if rows_at and k - 1 < len(rows_at) else k
        tc, vc, uc = cell(r, "t"), cell(r, "value"), cell(r, "unit")
        if parse_time(tc)[1] and parse_time(vc)[0] is not None:
            raise layout_refused(n, h["t"] + 1)
        if "unit" in h and vc and not re.search(r"\d", vc) and vc.lower() not in NOT_DONE_WORDS \
                and re.fullmatch(r"[<>]?=?\s*" + NUM, uc):
            raise layout_refused(n, h["value"] + 1)

def clean(text, synthetic_only=True, _melted=False, _rows_at=None):
    lines = [l for l in text.splitlines() if l.strip()]
    pipe = bool(lines) and all("|" in l for l in lines[:5])
    table = split(text)
    head, body = table[0], table[1:]
    h = header_map(head)
    if "t" not in h and "local_label" in h:          # wide paste: times across the columns
        strict_header(head, wide=True)
        melted, at = _melt(head, body, h, file_lines(text))
        return clean(melted, synthetic_only, _melted=True, _rows_at=at)   # rows keep the original paste's numbers
    if pipe:
        strict_header(head)
    missing = [c for c in ("local_label", "t", "value") if c not in h]
    if missing:
        raise Refused("NO_REQUIRED_COLUMN", f"Refused: no column recognised for {', '.join(missing)}.")
    rows_at = _rows_at if _melted else file_lines(text)
    swapped_columns(h, body, rows_at)
    pats = {r[h["patient"]].strip() for r in body if "patient" in h and len(r) > h["patient"] and r[h["patient"]].strip()}
    synthetic = bool(pats) and all(SYNTH.match(p) for p in pats)
    if synthetic_only and not synthetic:
        raise Refused("NOT_PROVABLY_SYNTHETIC", TRIPWIRE)
    if len(pats) > 1:
        raise Refused("MULTIPLE_PATIENTS", "Refused: this paste contains more than one patient.")
    rejects, rows, unreadable, no_time = [], [], [], 0
    get = lambda r, k: r[h[k]].strip() if k in h and h[k] < len(r) else ""
    lab2 = MAP.group_by("local_label").len()
    multi = set(lab2.filter(pl.col("len") > 1)["local_label"])
    lmap = {r["local_label"]: r for r in MAP.to_dicts()}
    for k, r in enumerate(body, start=2):
        i = rows_at[k - 1] if rows_at and k - 1 < len(rows_at) else k
        label = get(r, "local_label")
        if label in multi:
            rejects.append((i, "label", "matches more than one concept")); continue
        if label not in lmap or not lmap[label].get("concept_id"):
            rejects.append((i, "label", "not in mapping")); continue
        t, why = parse_time(get(r, "t"))
        if why:
            rejects.append((i, "time", why)); no_time += 1; continue
        not_done = get(r, "value").strip().lower() in NOT_DONE_WORDS     # 'not done' written in the value column
        if (not get(r, "value") and get(r, "status").lower() in ABSENT_STATUS) or not_done:   # a recorded absence
            val, status, extra = None, "absent", get(r, "gap_reason") or "recorded absence"
        else:
            val, status, extra = parse_value(get(r, "value"))
        if status == "reject":
            rejects.append((i, "value", extra)); unreadable.append((lmap[label]["concept_id"], t)); continue
        unit = get(r, "unit")
        if status != "absent" and not unit:
            rejects.append((i, "unit", "missing")); unreadable.append((lmap[label]["concept_id"], t)); continue
        conc = lmap[label]["concept_id"]
        if status != "absent":
            conv = UNITS.filter((pl.col("concept_id") == conc) & (pl.col("from_unit") == unit)) if "concept_id" in UNITS.columns \
                else UNITS.filter(pl.col("from_unit") == unit)
            if conv.height == 0:
                rejects.append((i, "unit", "no conversion")); unreadable.append((conc, t)); continue
            c = conv.row(0, named=True); val = val * c["factor"]; unit = c["to_unit"]
        rows.append(dict(line=i, local_label=label, concept_id=conc, t=t, value=val, unit=unit,
                         status=status, bound=extra if status == "censored" else None,
                         gap_reason=extra if status == "absent" else None,
                         result_status=(get(r, "value").strip().lower() if not_done else get(r, "status").lower()) or None,
                         device=get(r, "device") or None, specimen=get(r, "specimen") or None))
    if len({(r["concept_id"], r["unit"], r["device"], r["specimen"]) for r in rows}) > MAX_SERIES:
        raise Refused("TOO_MANY_SERIES", f"Refused: more than {MAX_SERIES} series in one paste.")
    rows, rejects, order = _order(rows, rejects)
    DUP_GAPS.clear()
    rows, rejects = _amended(rows, rejects)
    unreadable += DUP_GAPS
    df = pl.DataFrame(rows, schema={"line": pl.Int64, "local_label": pl.Utf8, "concept_id": pl.Utf8, "t": pl.Datetime,
                                    "value": pl.Float64, "unit": pl.Utf8, "status": pl.Utf8, "bound": pl.Utf8,
                                    "gap_reason": pl.Utf8, "result_status": pl.Utf8, "device": pl.Utf8,
                                    "specimen": pl.Utf8}).sort(["concept_id", "t"])
    res = Result(df, rejects, synthetic, identity_verified=len(pats) == 1, order=order,
                 unreadable=unreadable, no_time=no_time)
    res.patient = next(iter(pats)) if pats else None   # the paste's own id (never a hard-coded one)
    return res

def _melt(head, body, h, at=None):
    """Wide to long. Also returns, per melted line, the original paste's row number (header = row 1)."""
    li = h["local_label"]
    out = ["local_label\tt\tvalue\tunit" + ("\tpatient" if "patient" in h else "")]
    rows = [at[0] if at else 1]
    ui = h.get("unit")
    for b, r in enumerate(body, 1):
        for j, col in enumerate(head):
            if j in h.values() or j >= len(r) or not r[j].strip():
                continue
            out.append("\t".join([r[li], col, r[j], r[ui] if ui is not None else ""] +
                                 ([r[h["patient"]]] if "patient" in h else [])))
            rows.append(at[b] if at and b < len(at) else b + 1)
    return "\n".join(out), rows

def _order(rows, rejects):
    """Time direction is decided once per paste. Reversed is fine; mixed or interleaved is refused."""
    by = {}
    for r in rows:
        by.setdefault(r["concept_id"], []).append(r["t"])
    dirs = set()
    for c, ts in by.items():
        d = [b > a for a, b in zip(ts, ts[1:]) if a != b]
        if not d:
            continue
        if all(d): dirs.add("oldest-first")
        elif not any(d): dirs.add("newest-first")
        else:
            raise Refused("INTERLEAVED_TIME", f"Refused: time goes forwards then backwards within {c}; this may be two charts stitched together.")
    if len(dirs) > 1:
        raise Refused("MIXED_TIME_ORDER", "Refused: series in this paste run in different time orders; this may be two copies stitched together.")
    return rows, rejects, (dirs.pop() if dirs else "oldest-first")

def _amended(rows, rejects):
    """Same series, same time, same specimen and source: keep the final result; if unclear, reject all."""
    key = lambda r: (r["concept_id"], r["t"], r["specimen"], r["device"])
    groups = {}
    for r in rows:
        groups.setdefault(key(r), []).append(r)
    keep = []
    for g in groups.values():
        if len(g) == 1 or len({x["value"] for x in g}) == 1:
            keep.append(g[0]); continue
        final = [x for x in g if x["result_status"] in ("final", "amended", "corrected")]
        if len(final) == 1:
            keep.append(final[0])
        else:
            rejects += [(x["line"], "status", "duplicate result, unclear which is final") for x in g]
            DUP_GAPS.extend((x["concept_id"], x["t"]) for x in g)
    return keep, rejects

DUP_GAPS = []

# ---------- real-data entry ----------
def from_file(path):
    return clean(Path(path).read_text(), synthetic_only=False)

def from_clipboard():
    for cmd in (["wl-paste"], ["xclip", "-o", "-selection", "clipboard"], ["pbpaste"]):
        try:
            return clean(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout, synthetic_only=False)
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
    raise Refused("NO_CLIPBOARD", "Refused: no clipboard reader available on this machine.")

def to_parquet(res, path):
    if not res.synthetic:
        raise Refused("REAL_DATA_NOT_WRITTEN", "Refused: real data is never written to disk.")
    res.rows.write_parquet(path)

if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        res = from_clipboard() if "--clipboard" in a else from_file(a[a.index("--file") + 1]) if "--file" in a \
            else clean(sys.stdin.read())
    except Refused as e:
        print(json.dumps({"error": e.code, "message": e.message}), file=sys.stderr); sys.exit(2)
    print(json.dumps(res.summary(), default=str, indent=1))
