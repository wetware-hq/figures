"""figures v0: pasted raw table in -> one-file HTML gallery of trajectory figures with legends.
Usage:  pbpaste | python figures.py  (or: python figures.py export.csv)  -> gallery.html
Rules: no interpolation; line breaks at every absence and at any gap > 1.5x the series' usual interval;
tick strip shows when measurements happened; unmapped rows shown on the chart; no points CSV (Class B)."""
import sys, io, base64, html, subprocess, secrets, re
from pathlib import Path
import polars as pl, matplotlib; matplotlib.use("Agg")
import clean as cleaner
import matplotlib.pyplot as plt, matplotlib.dates
HERE = Path(__file__).parent
plt.style.use(HERE / "default.mplstyle")
DISPLAY = dict(pl.read_csv(HERE / "concepts.csv").iter_rows())

# ---------- synthetic-date safeguard ----------
# Its own copy of the same logic letters uses (no cross-repo dependency); the same boundary tests run in both.
SYNTH_FIRST, SYNTH_LAST = "1930-01-01", "1939-12-31"
SCAN_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
SCAN_DMY = re.compile(r"(?<![\d.])(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})(?![\d.])")
DATE_REFUSED = ("Refused: row {n} of the paste has a date outside 1 Jan 1930 to 31 Dec 1939. Nothing was saved.\n"
                "If this is real data, delete the paste and use synthetic data only.")

class DateRefused(Exception):
    def __init__(self, row):
        super().__init__("date outside range"); self.row = row

def date_in_range(y, mo, d):
    """True only for a real calendar date from SYNTH_FIRST to SYNTH_LAST."""
    import datetime as _dt
    try: _dt.date(y, mo, d)
    except ValueError: return False
    return SYNTH_FIRST <= f"{y:04d}-{mo:02d}-{d:02d}" <= SYNTH_LAST

def first_out_of_range_line(text):
    """1-based row of the original paste (blank lines counted) with the first date outside the range; None if none."""
    for n, line in enumerate(text.splitlines(), 1):
        for m in SCAN_ISO.finditer(line):
            if not date_in_range(*(int(x) for x in m.groups())): return n
        for m in SCAN_DMY.finditer(line):
            d, mo, y = (int(x) for x in m.groups())
            if not date_in_range(y + 1900 if y < 100 else y, mo, d): return n
    return None

def check_dates(text):
    n = first_out_of_range_line(text)
    if n: raise DateRefused(n)

class NoRows(Exception):
    """No usable rows after cleaning. Carries the first rejected data row number only."""
    def __init__(self, row=None):
        super().__init__("no usable rows"); self.row = row

class SemicolonPaste(Exception):
    def __init__(self, row=None):
        super().__init__("semicolon"); self.row = row

SEMICOLON_REFUSED = "Refused: semicolon-separated pastes aren't supported. Use commas or tabs."
SEMICOLON_ROW = "Refused: semicolon-separated pastes aren't supported (row {n}). Use commas or tabs."
GAP_LEGEND = "Gap: a result was recorded here but couldn't be read."
BELOW_LEGEND = "▼ below the test's limit (<{x}). The real value is lower than shown. (row {n})"
ABOVE_LEGEND = "▲ above the test's limit (>{x}). The real value is higher than shown. (row {n})"
NOT_DONE_LEGEND = "✕ Not done: no test was done at this time."
NO_RANGE_FLAG = "Flag: no normal range on file for the test on row {n}. It's charted without one."
NOT_DONE = {"missed", "not done", "not collected"}

def _rows(rows):
    rs = sorted(set(rows))
    return f"(row {rs[0]})" if len(rs) == 1 else f"(rows {', '.join(str(r) for r in rs)})"

def count_line(gap_rows, time_rows, label_rows):
    """Signed: '3 values couldn't be read and aren't shown: 1 is marked as a gap (row 4), 1 has no readable time
    (row 7), 1 has a test name we didn't recognise (row 7).' One entry per value (a wide-paste row can hold several);
    rows from the original paste. A part only when nonzero; verbs match the number; parts add up to the total."""
    a, b, c = len(gap_rows), len(time_rows), len(label_rows)
    n = a + b + c
    if not n: return ""
    parts = []
    if a: parts.append(f"{a} is marked as a gap {_rows(gap_rows)}" if a == 1 else f"{a} are marked as gaps {_rows(gap_rows)}")
    if b: parts.append(f"{b} has no readable time {_rows(time_rows)}" if b == 1 else f"{b} have no readable time {_rows(time_rows)}")
    if c: parts.append(f"1 has a test name we didn't recognise {_rows(label_rows)}" if c == 1 else
                       f"{c} have test names we didn't recognise {_rows(label_rows)}")
    return f"{n} {'value' if n == 1 else 'values'} couldn't be read and {'isn' if n == 1 else 'aren'}'t shown: " + ", ".join(parts) + "."

def load(text):
    """Every paste goes through clean.py (the one parser). Returns (rows, unmapped count, patient, as_at)."""
    nonblank = [l for l in text.splitlines() if l.strip()]
    first = nonblank[0] if nonblank else ""
    if ";" in first and not any(d in first for d in ("\t", ",", "|")):
        all_lines = text.splitlines()
        raise SemicolonPaste(next((n for n in cleaner.file_lines(text)[1:] if ";" in all_lines[n - 1]), None))
    res = cleaner.clean(text)                       # synthetic only; refuses anything else
    table = cleaner.split(text); h = cleaner.header_map(table[0])
    pats = [r[h["patient"]].strip() for r in table[1:] if "patient" in h and len(r) > h["patient"] and r[h["patient"]].strip()]
    ats = [r[h["as_at"]].strip() for r in table[1:] if "as_at" in h and len(r) > h["as_at"] and r[h["as_at"]].strip()]
    if res.rows.height == 0:
        raise NoRows(min((ln for ln, _, _ in res.rejects), default=1) if res.rejects else None)
    d = res.rows.with_columns(pl.lit(pats[0]).alias("patient"), pl.col("unit").alias("map_unit"),
                              pl.col("value").alias("v"))
    if res.unreadable:                               # dropped rows with a readable time: a gap at their own time
        gaps = pl.DataFrame({"concept_id": [c for c, _ in res.unreadable], "t": [t for _, t in res.unreadable]},
                            schema={"concept_id": pl.Utf8, "t": pl.Datetime})
        units = d.select("concept_id", "unit").unique(subset="concept_id")
        gaps = gaps.join(units, on="concept_id", how="inner").with_columns(
            pl.lit(pats[0]).alias("patient"), pl.lit("unreadable").alias("status"), pl.col("unit").alias("map_unit"))
        d = pl.concat([d, gaps], how="diagonal_relaxed").sort(["concept_id", "t"])
    n_unmapped = sum(1 for _, f, _ in res.rejects if f in ("label", "unit"))
    global COUNT_LINE
    by = lambda fields: [ln for ln, f, _ in res.rejects if f in fields]       # original paste rows, one per value
    COUNT_LINE = count_line(by(("value", "unit", "status")), by(("time",)), by(("label",)))
    return d, n_unmapped, pats[0], (max(ats) if ats else None)

COUNT_LINE = ""
NOTICES = []

def segments(s, limit):
    """Runs of measured points; a run ends at a recorded absence, or (cosmetic only) after > limit with no result."""
    s = s.sort("t")
    runs, cur, last = [], [], None
    for row in s.iter_rows(named=True):
        if row["status"] == "censored":
            last = row["t"] if cur else last         # a marked limit: a result was taken (no gap), but never a trend point
            continue
        if row["status"] != "measured":
            if cur: runs.append(cur); cur = []
            continue
        if cur and limit is not None and row["t"] - last > limit:
            runs.append(cur); cur = []
        cur.append(row); last = row["t"]
    if cur: runs.append(cur)
    return runs

def absences(s, not_done=True):
    """Recorded absences. With not_done=False, 'not done', 'missed' and 'not collected' are left out: they are never gaps."""
    keep = ~pl.col("status").is_in(["measured", "censored"])     # a value beyond the test's limit is a result, not a gap
    if not not_done:
        keep = keep & ~((pl.col("status") == "absent") & pl.col("result_status").fill_null("").is_in(list(NOT_DONE)))
    a = s.filter(keep).sort("t")["t"].to_list()
    spans, start = [], None
    for i, t in enumerate(a):
        start = start or t
        if i + 1 == len(a) or (a[i + 1] - t).days > 1:
            spans.append((start, t)); start = None
    return spans

from datetime import datetime
DRAWN = datetime.now().replace(second=0, microsecond=0)
ANCHOR = {"t": DRAWN, "label": "this chart was made"}  # replaced by data as-at when supplied

def between(a, b):
    """The one string for elapsed time between two results; used on the chart and in the legend."""
    h = (b - a).total_seconds() / 3600
    return f"{h/24:.0f} days ({h:.0f} h) between results" if h >= 48 else f"{h:.0f} h between results"

def line_pieces(run, censored_times):
    """Split a run's drawn line wherever a censored marker sits between two results. Gap timing is unchanged
    (the run is still one run); only the drawn line stops short of the marker on both sides."""
    pieces, cur = [], []
    for p in run:
        if cur and any(cur[-1]["t"] <= c <= p["t"] for c in censored_times):
            pieces.append(cur); cur = []
        cur.append(p)
    if cur: pieces.append(cur)
    return pieces

def draw(s, concept, unit, patient, n_unmapped, mapping_ver, limit, mode="ward"):
    """One axes, x = time, y = value. Nothing else."""
    fig, ax = plt.subplots(figsize=(4.21, 2.9))
    runs = segments(s, limit)
    cens = s.filter(pl.col("status") == "censored")["t"].to_list()
    for r in runs:
        for piece in line_pieces(r, cens):          # no trend line into or out of a censored marker
            ax.plot([p["t"] for p in piece], [p["v"] for p in piece], marker="o", color="C0")
    last = runs[-1][-1] if runs else None
    if last and len(runs[-1]) == 1:
        ax.plot([last["t"]], [last["v"]], marker="o", mfc="white", color="C0", zorder=3)
    if runs:
        b0 = runs[0][0]
        ax.axhline(b0["v"], color="0.6", lw=0.8)
        ax.text(0.01, b0["v"], f" admission value, {b0['t']:%d %b}", transform=ax.get_yaxis_transform(), fontsize=6, va="bottom")
    pad = (limit or (runs[-1][-1]["t"] - runs[0][0]["t"])) * 0.08 if runs else None
    for prev, nxt in zip(runs, runs[1:]):   # shade the whole span between results, small margin at each dot
        a, b = prev[-1]["t"], nxt[0]["t"]
        ax.axvspan(a + pad, b - pad, color="0.9", lw=0)
        ax.text(a + (b - a) / 2, 0.97, between(a, b).replace(" between", "\nbetween"), transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=6.5)
    if last:
        age = (ANCHOR["t"] - last["t"]).total_seconds() / 3600
        ax.annotate(f"last measured {last['t']:%d %b %H:%M},\n{age:.0f} h before {ANCHOR['label']}",
                    (last["t"], last["v"]), xytext=(4, 30), textcoords="offset points", ha="right", arrowprops=dict(arrowstyle="-", color="0.4", lw=0.6), fontsize=6.5)
    for p in s.filter(pl.col("status") == "censored").iter_rows(named=True):
        below = str(p.get("bound") or "").startswith("<")    # a marked limit, not a point: bar at the limit + arrow
        ax.plot([p["t"]], [p["v"]], marker="_", markersize=12, mew=1.4, color="C3", ls="none", zorder=4)
        ax.plot([p["t"]], [p["v"]], marker="v" if below else "^", markersize=5, color="C3", ls="none", zorder=4,
                markevery=None, transform=ax.transData)
    tr = ax.get_xaxis_transform()
    for p in s.filter(pl.col("status") == "unreadable").iter_rows(named=True):
        ax.axvline(p["t"], color="0.5", ls=":", lw=0.8)
    for p in s.filter((pl.col("status") == "absent") & pl.col("result_status").is_in(list(NOT_DONE))).iter_rows(named=True):
        ax.plot([p["t"]], [0.04], marker="x", color="0.35", ls="none", transform=tr, zorder=4)
    name = DISPLAY.get(concept, concept)
    ax.set_ylabel(f"{name} ({unit})")
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))
    if mode == "journal":
        fig.text(0.5, 0.5, "NOT FOR CLINICAL USE", ha="center", va="center", fontsize=18, color="C1", alpha=0.35, rotation=20)
    meas = s.filter(pl.col("status") == "measured")["t"].to_list()
    return fig, runs, meas

MAX_LINE1 = 220

def synopsis(s, runs, row, unit):
    """Line 1. Hand-back first; analyte only, never the patient. Withheld unless limits row is SIGNED."""
    pts = [p for r in runs for p in r]
    hand = "Read with the bedside."
    if len(pts) < 2: return f"{hand} Too few results to describe."
    v0, vl, t0, tl = pts[0]["v"], pts[-1]["v"], pts[0]["t"], pts[-1]["t"]
    nums = f"{v0:g} to {vl:g} {unit} ({t0:%d %b} to {tl:%d %b})"
    if row.get("status") != "SIGNED":
        return (f"{hand} {v0:g} {unit} on {t0:%d %b}; latest {vl:g} {unit} on {tl:%d %b}, {between(pts[-2]['t'], tl)}."
                " Interpretation withheld until test limits are signed off.")
    # signed path: trend words only when the signed threshold allows them
    hl = row.get("expected_half_life_h"); fall = row.get("rcv_fall_pct"); rise = row.get("rcv_rise_pct")
    ch = (vl - v0) / v0 * 100 if v0 else 0
    if hl and vl < v0: trend, kin = "Fell", f"at about the expected rate for {DISPLAY.get(pts[0]['concept_id'], pts[0]['concept_id'])}"
    elif fall and ch <= -float(fall): trend, kin = "Fell", ""
    elif rise and ch >= float(rise): trend, kin = "Rose", ""
    else: trend, kin = "Changed", "within test noise"
    alts = "possible reasons need the clinical picture"
    for line in (f"{hand} {trend} {kin} from {nums}; {alts}.", f"{hand} {trend} {kin}; {alts}.", f"{hand} {trend}; {alts}."):
        line = re.sub(" +", " ", line)
        if len(line) <= MAX_LINE1: return line   # numbers go first, then kinetics; alternatives + hand-back never go
    return line

SOURCE_NOT_GIVEN = "source not given"   # no signed wording in README/DECISIONS; spec wording

def source_text(s):
    src = ", ".join(sorted(x for x in set(s["device"].drop_nulls()) if x.strip()))
    return f"source {src}" if src else SOURCE_NOT_GIVEN

def legend_text(concept, unit, s, runs, n_unmapped, mapping_ver, limit_h, row):
    rec = len(absences(s, not_done=False)); inferred = max(len(runs) - 1 - len(absences(s)), 0)
    e = html.escape
    return (f"<b>{e(synopsis(s, runs, row, unit))}</b><br>"
            f"<i>For the clinical team:</i> {e(DISPLAY.get(concept, concept))} ({e(unit)}), single patient not verified, {e(frequency(s))}, {e(source_text(s))}, admission baseline, {rec} gap recorded, {inferred} inferred "
            + (f"(&gt;{limit_h:g} h)" if limit_h else "(no normal range or gap limit on file)")
            + f", {n_unmapped} results unmapped, limits {e(row.get('status','none on file')).lower()}, mapping {mapping_ver}, drawn {DRAWN:%d %b %Y %H:%M}.")

def marker_legend(s):
    """Fixed legend lines for the markers actually drawn; values only, never pasted text."""
    out = []
    if s.filter(pl.col("status") == "unreadable").height: out.append(GAP_LEGEND)
    cen = s.filter(pl.col("status") == "censored")
    for p in cen.iter_rows(named=True):
        line = (BELOW_LEGEND if str(p.get("bound") or "").startswith("<") else ABOVE_LEGEND).format(
            x=f"{p['v']:g}", n=p.get("line") or "not known")
        if line not in out: out.append(line)
    if s.filter((pl.col("status") == "absent") & pl.col("result_status").is_in(list(NOT_DONE))).height: out.append(NOT_DONE_LEGEND)
    return "".join(f"<br>{html.escape(x)}" for x in out)

def frequency(s):
    t = s.filter(pl.col("status").is_in(["measured", "censored"])).sort("t")["t"]
    h = [x.total_seconds() / 3600 for x in t.diff().drop_nulls()]
    if len(h) < 4: return f"{len(t)} results"
    import statistics as st
    k = len(h) // 2; a, b = st.median(h[:k]), st.median(h[k:])
    if b >= 2 * a: return f"{len(t)} results, every ~{a:.0f} h then every ~{b:.0f} h from {t[k]:%d %b}"
    return f"{len(t)} results, usually every ~{st.median(h):.0f} h"

def build(text, out="gallery.html", mode="ward", as_at=None):
    NOTICES.clear()
    check_dates(text)
    d, n_unmapped, patient, paste_as_at = load(text)
    if as_at is None: as_at = paste_as_at
    if as_at is not None:
        ANCHOR.update(t=datetime.fromisoformat(str(as_at)), label=f"data as-at {datetime.fromisoformat(str(as_at)):%d %b %H:%M}")
    else:
        ANCHOR.update(t=DRAWN, label="this chart was made")
    future = d.filter((pl.col("status") == "measured") & (pl.col("t") > ANCHOR["t"]))
    if future.height:
        raise SystemExit(f"REFUSED: {future.height} result(s) dated after {ANCHOR['label']} (first {future['t'].min()}). Clock or data error.")
    try: ver = subprocess.run(["git", "-C", str(HERE), "log", "-1", "--format=%h", "--", "mapping.csv", "units.csv", "limits.csv"],
                              capture_output=True, text=True).stdout.strip() or "uncommitted"
    except Exception: ver = "uncommitted"
    limits = pl.read_csv(HERE / "limits.csv", comment_prefix="#")
    outdir = Path(out).with_suffix(""); outdir.mkdir(exist_ok=True)
    cards, checks, legends = [], [], []
    for (patient, concept), s in d.group_by(["patient", "concept_id"], maintain_order=True):
        unit = s["map_unit"].drop_nulls()[0]
        nu = n_unmapped
        row = limits.filter(pl.col("concept_id") == concept); lim = row["gap_limit_h"]
        from datetime import timedelta
        if lim.is_empty():                           # no normal range on file: charted without one, never shown as normal
            limit_h = None
            first_row = int(s["line"].drop_nulls().min()) if "line" in s.columns and s["line"].drop_nulls().len() else 1
            NOTICES.append(NO_RANGE_FLAG.format(n=first_row))
        else:
            limit_h = float(lim[0])
        fig, runs, meas = draw(s, concept, unit, patient, nu, ver, timedelta(hours=limit_h) if limit_h else None, mode)
        checks.append((s, runs, fig))
        n = len(cards) + 1
        rid = secrets.token_hex(2)                   # random per draw; never derived from the data (Class B)
        lim_row = row.row(0, named=True) if row.height else {}
        withheld = lim_row.get("status") != "SIGNED"
        foot = " · ".join(x for x in ["Synthetic data" if str(patient).startswith("SYNTH") else None, "Single-patient chart, identity not verified",
                                       "Read with the bedside", "Interpretation withheld" if withheld else None,
                                       f"Fig {n}, render {rid}"] if x)   # capped footer: changes need maintainer sign-off
        fig.text(0.99, 0.005, foot, ha="right", va="bottom", fontsize=5.5, color="0.45")
        for ext in ("png", "svg", "pdf"):           # image carries only the capped footer, no legend
            fig.savefig(outdir / f"figure_{n}.{ext}", metadata={"Description" if ext == "png" else "Title": f"render {rid}"})
        plt.close(fig)
        leg = legend_text(concept, unit, s, runs, nu, ver, limit_h, lim_row) + marker_legend(s)
        if limit_h is None:
            leg += "<br>" + html.escape(NOTICES[-1])
        legends.append(f"**Figure {n}** (render {rid})**.** " + html.unescape(leg.replace("<br>", " ").replace("<b>", "").replace("</b>", "")
                       .replace("<i>", "*").replace("</i>", "*")))
        cards.append(f"<figure><img src='figure_{n}.png'><figcaption><b>Figure {n}</b> (render {rid}). {leg}</figcaption></figure>")
    page = ("<!doctype html><meta charset=utf-8><title>figures</title><style>body{font:14px sans-serif;max-width:760px;"
            "margin:2em auto}figure{margin:0 0 3em}img{width:100%}figcaption{font-size:13px;line-height:1.4}</style>"
            f"<p>{len(cards)} figures. SYNTHETIC DATA ONLY. Real patient trajectories are shown on screen or printed, never saved as this file.</p>"
            + (f"<p class=count>{html.escape(COUNT_LINE)}</p>" if COUNT_LINE else "") + "".join(cards))
    (outdir / "legends.md").write_text("# Figure legends\n\nSYNTHETIC DATA ONLY.\n\n" + (COUNT_LINE + "\n\n" if COUNT_LINE else "")
                                       + "\n\n".join(legends) + "\n")
    (outdir / "index.html").write_text(page); return str(outdir), checks

def verify(outdir):
    """Refuse a gallery whose legend entries and images don't share a render ID."""
    from PIL import Image
    outdir = Path(outdir); want = dict(re.findall(r"\*\*Figure (\d+)\*\* \(render ([0-9a-f]+)\)", (outdir / "legends.md").read_text()))
    for n, rid in want.items():
        got = Image.open(outdir / f"figure_{n}.png").info.get("Description", "")
        if got != f"render {rid}":
            raise SystemExit(f"REFUSED: Figure {n} legend is render {rid} but image is '{got}'. Re-render both.")
    return True

LAYOUT_ROW = "Refused: row {n} doesn't match the expected layout."
LAYOUT_ANY = "Refused: no rows in the expected layout were found. Nothing was saved."

def bad_row(text, e=None):
    """First row (spreadsheet style: the file's own line number, header = row 1) that breaks the layout, using clean.py's reader; None if unknown.
    Never returns row text."""
    if isinstance(e, NoRows): return None          # nothing usable: the 'no rows' refusal, never a row number
    try:
        table = cleaner.split(text)
        head, h = table[0], cleaner.header_map(table[0])
        if not {"local_label", "t", "value"} <= set(h): return None
        at = cleaner.file_lines(text)
        for k, r in enumerate(table[1:], 1):
            n = at[k] if k < len(at) else k + 1
            if len(r) != len(head): return n
            if cleaner.parse_time(r[h["t"]])[1]: return n
    except Exception:
        return None
    return None

def main(argv):
    """One top-level guard: any failure becomes one fixed line (row number only), exit 2, nothing written."""
    out = Path("gallery.html").with_suffix("")
    existed = out.exists()
    text = ""
    try:
        if argv[:1] == ["--verify"]: print(verify(argv[1])); return 0
        args = [a for a in argv if not a.startswith("--as-at=")]
        as_at = next((a.split("=", 1)[1] for a in argv if a.startswith("--as-at=")), None)
        text = Path(args[0]).read_text() if args else sys.stdin.read()
        result = build(text, as_at=as_at)[0]
    except BaseException as e:
        if isinstance(e, SystemExit) and e.code in (0, None): return 0
        if not existed and out.exists():
            import shutil; shutil.rmtree(out, ignore_errors=True)
        n = None if isinstance(e, DateRefused) else bad_row(text, e)
        if isinstance(e, DateRefused):
            msg = DATE_REFUSED.format(n=e.row)
        elif isinstance(e, SemicolonPaste):
            msg = SEMICOLON_ROW.format(n=e.row) if e.row else SEMICOLON_REFUSED
        elif isinstance(e, cleaner.Refused) and e.code == "LAYOUT":
            msg = e.message                         # row and column only
        else:
            msg = LAYOUT_ROW.format(n=n) if n else LAYOUT_ANY
        sys.stderr.write(msg + "\n")
        return 2
    for note in NOTICES:
        sys.stderr.write(note + "\n")
    print(result)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
