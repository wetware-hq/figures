"""figures v0: pasted raw table in -> one-file HTML gallery of trajectory figures with legends.
Usage:  pbpaste | python figures.py  (or: python figures.py export.csv)  -> gallery.html
Rules: no interpolation; line breaks at every absence and at any gap > 1.5x the series' usual interval;
tick strip shows when measurements happened; unmapped rows shown on the chart; no points CSV (Class B)."""
import sys, io, base64, html, subprocess
from pathlib import Path
import polars as pl, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates
HERE = Path(__file__).parent
plt.style.use(HERE / "default.mplstyle")
DISPLAY = dict(pl.read_csv(HERE / "concepts.csv").iter_rows())

def read_table(text):
    sep = "\t" if text.count("\t") > text.count(",") else ","
    return pl.read_csv(io.StringIO(text.strip()), separator=sep, try_parse_dates=True, infer_schema_length=0)

def prepare(raw):
    m = pl.read_csv(HERE / "mapping.csv", infer_schema_length=0)
    u = pl.read_csv(HERE / "units.csv")
    d = (raw.with_columns(pl.col("t").str.to_datetime(), pl.col("value").cast(pl.Float64, strict=False))
            .join(m.rename({"unit": "map_unit"}), on="local_label", how="left"))
    unmapped = d.filter(pl.col("concept_id").is_null() | (pl.col("concept_id") == ""))
    d = (d.filter(pl.col("concept_id").is_not_null() & (pl.col("concept_id") != ""))
          .join(u, left_on="unit", right_on="from_unit", how="left")
          .with_columns((pl.col("value") * pl.col("factor")).alias("v")))
    bad_unit = d.filter(pl.col("factor").is_null() & (pl.col("status") == "measured"))
    return d.filter(pl.col("factor").is_not_null() | (pl.col("status") != "measured")), unmapped, bad_unit

def segments(s, limit):
    """Runs of measured points; a run ends at a recorded absence, or (cosmetic only) after > limit with no result."""
    s = s.sort("t")
    runs, cur, last = [], [], None
    for row in s.iter_rows(named=True):
        if row["status"] != "measured":
            if cur: runs.append(cur); cur = []
            continue
        if cur and limit is not None and row["t"] - last > limit:
            runs.append(cur); cur = []
        cur.append(row); last = row["t"]
    if cur: runs.append(cur)
    return runs

def absences(s):
    a = s.filter(pl.col("status") != "measured").sort("t")["t"].to_list()
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

def draw(s, concept, unit, patient, n_unmapped, mapping_ver, limit, mode="ward"):
    """One axes, x = time, y = value. Nothing else."""
    fig, ax = plt.subplots(figsize=(4.21, 2.9))
    runs = segments(s, limit)
    for r in runs:
        ax.plot([p["t"] for p in r], [p["v"] for p in r], marker="o", color="C0")
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

def legend_text(concept, unit, s, runs, n_unmapped, mapping_ver, limit_h, row):
    rec = len(absences(s)); inferred = max(len(runs) - 1 - rec, 0)
    e = html.escape
    return (f"<b>{e(synopsis(s, runs, row, unit))}</b><br>"
            f"<i>For the clinical team:</i> {e(DISPLAY.get(concept, concept))} ({e(unit)}), one patient, {e(frequency(s))}, source {e(', '.join(sorted(set(s['device'].drop_nulls()))))}, admission baseline, {rec} gap recorded, {inferred} inferred "
            f"(&gt;{limit_h:g} h), {n_unmapped} results unmapped, limits {e(row.get('status','?')).lower()}, mapping {mapping_ver}, drawn {DRAWN:%d %b %Y %H:%M}.")

def png_b64(fig):
    b = io.BytesIO(); fig.savefig(b, format="png"); plt.close(fig); return base64.b64encode(b.getvalue()).decode()

def frequency(s):
    t = s.filter(pl.col("status") == "measured").sort("t")["t"]
    h = [x.total_seconds() / 3600 for x in t.diff().drop_nulls()]
    if len(h) < 4: return f"{len(t)} results"
    import statistics as st
    k = len(h) // 2; a, b = st.median(h[:k]), st.median(h[k:])
    if b >= 2 * a: return f"{len(t)} results, every ~{a:.0f} h then every ~{b:.0f} h from {t[k]:%d %b}"
    return f"{len(t)} results, usually every ~{st.median(h):.0f} h"

def build(text, out="gallery.html", mode="ward", as_at=None):
    raw = read_table(text)
    if as_at is None and "as_at" in raw.columns: as_at = raw["as_at"].drop_nulls().max()
    if as_at is not None:
        ANCHOR.update(t=datetime.fromisoformat(str(as_at)), label=f"data as-at {datetime.fromisoformat(str(as_at)):%d %b %H:%M}")
    else:
        ANCHOR.update(t=DRAWN, label="this chart was made")
    d, unmapped, bad = prepare(raw)
    future = d.filter((pl.col("status") == "measured") & (pl.col("t") > ANCHOR["t"]))
    if future.height:
        raise SystemExit(f"REFUSED: {future.height} result(s) dated after {ANCHOR['label']} (first {future['t'].min()}). Clock or data error.")
    try: ver = subprocess.run(["git", "-C", str(HERE), "log", "-1", "--format=%h", "--", "mapping.csv", "units.csv", "limits.csv"],
                              capture_output=True, text=True).stdout.strip() or "uncommitted"
    except Exception: ver = "uncommitted"
    limits = pl.read_csv(HERE / "limits.csv")
    outdir = Path(out).with_suffix(""); outdir.mkdir(exist_ok=True)
    cards, checks, legends = [], [], []
    for (patient, concept), s in d.group_by(["patient", "concept_id"], maintain_order=True):
        unit = s["map_unit"].drop_nulls()[0]
        nu = unmapped.filter(pl.col("patient") == patient).height + bad.filter(pl.col("patient") == patient).height
        row = limits.filter(pl.col("concept_id") == concept); lim = row["gap_limit_h"]
        if lim.is_empty(): raise SystemExit(f"No signed-off gap limit for {concept} in limits.csv")
        limit_h = float(lim[0]); from datetime import timedelta
        fig, runs, meas = draw(s, concept, unit, patient, nu, ver, timedelta(hours=limit_h), mode)
        checks.append((s, runs, fig))
        n = len(cards) + 1
        for ext in ("png", "svg", "pdf"):           # image files carry no legend text
            fig.savefig(outdir / f"figure_{n}.{ext}")
        plt.close(fig)
        leg = legend_text(concept, unit, s, runs, nu, ver, limit_h, row.row(0, named=True))
        legends.append(f"**Figure {n}.** " + html.unescape(leg.replace("<br>", " ").replace("<b>", "").replace("</b>", "")
                       .replace("<i>", "*").replace("</i>", "*")))
        cards.append(f"<figure><img src='figure_{n}.png'><figcaption><b>Figure {n}.</b> {leg}</figcaption></figure>")
    page = ("<!doctype html><meta charset=utf-8><title>figures</title><style>body{font:14px sans-serif;max-width:760px;"
            "margin:2em auto}figure{margin:0 0 3em}img{width:100%}figcaption{font-size:13px;line-height:1.4}</style>"
            f"<p>{len(cards)} figures. SYNTHETIC DATA ONLY. Real patient trajectories are shown on screen or printed, never saved as this file.</p>"
            + "".join(cards))
    (outdir / "legends.md").write_text("# Figure legends\n\nSYNTHETIC DATA ONLY.\n\n" + "\n\n".join(legends) + "\n")
    (outdir / "index.html").write_text(page); return str(outdir), checks

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--as-at=")]
    as_at = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--as-at=")), None)
    text = Path(args[0]).read_text() if args else sys.stdin.read()
    print(build(text, as_at=as_at)[0])
