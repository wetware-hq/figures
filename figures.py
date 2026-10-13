"""figures v0: pasted raw table in -> one-file HTML gallery of trajectory figures with legends.
Usage:  pbpaste | python figures.py  (or: python figures.py export.csv)  -> gallery.html
Rules: no interpolation; line breaks at every absence and at any gap > 1.5x the series' usual interval;
tick strip shows when measurements happened; unmapped rows shown on the chart; no points CSV (Class B)."""
import sys, io, base64, html, subprocess
from pathlib import Path
import polars as pl, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = Path(__file__).parent
plt.style.use(HERE / "default.mplstyle")

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

def draw(s, concept, unit, patient, n_unmapped, mapping_ver, limit, mode="ward"):
    fig, (ax, strip) = plt.subplots(2, 1, sharex=True, height_ratios=[6, 1], figsize=(4.21, 3.3))
    runs = segments(s, limit)
    for r in runs:
        ax.plot([p["t"] for p in r], [p["v"] for p in r], marker="o", color="C0")
    last = runs[-1][-1] if runs else None
    if last and len(runs[-1]) == 1:  # isolated latest point: hollow
        ax.plot([last["t"]], [last["v"]], marker="o", mfc="white", color="C0", zorder=3)
    base = runs[0][0]["v"] if runs else None
    if base is not None:
        ax.axhline(base, color="0.5", lw=0.8)
        ax.text(0.01, base, f" baseline: admission value, {runs[0][0]['t']:%d %b}", transform=ax.get_yaxis_transform(),
                fontsize=6, va="bottom")
    for a, b in absences(s):
        ax.axvspan(a, b, color="0.9", lw=0)
        ax.text(a + (b - a) / 2, ax.get_ylim()[1] * 0.95, f"not measured,\n{(b - a).days + 1} days",
                ha="center", va="top", fontsize=6.5)
    if last:
        ax.annotate(f"last measured\n{last['t']:%d %b %H:%M}", (last["t"], last["v"]), xytext=(0, 10),
                    textcoords="offset points", ha="center", fontsize=6.5)
    if n_unmapped:
        fig.text(0.99, 0.01, f"{n_unmapped} measurements not shown (unmapped)",
                ha="right", fontsize=6, color="C1")
    meas = s.filter(pl.col("status") == "measured")["t"].to_list()
    strip.vlines(meas, 0, 1, color="k", lw=0.8); strip.set_yticks([]); strip.set_ylim(0, 1)
    strip.spines["left"].set_visible(False)
    strip.set_ylabel("measured", rotation=0, ha="right", va="center", fontsize=6)
    ax.set_ylabel(f"{concept} ({unit})"); ax.set_title(f"{concept}, one patient")
    fig.autofmt_xdate()
    if mode == "test":  # strip nothing that makes the chart work; only the explanatory title
        ax.set_title("")
    if mode == "journal":
        fig.text(0.5, 0.5, "NOT FOR CLINICAL USE", ha="center", va="center", fontsize=18, color="C1", alpha=0.35, rotation=20)
    fig.text(0, 0, f"Source: {patient}; mapping {mapping_ver}", fontsize=5.5)
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
        gap_h = (tl - pts[-2]["t"]).total_seconds() / 3600
        un = sum((b - a).days + 1 for a, b in absences(s))
        return (f"{hand} {v0:g} {unit} on {t0:%d %b}; latest {vl:g} {unit} on {tl:%d %b}, {gap_h:.0f} h after the previous result"
                + (f", with {un} days unmeasured" if un else "") + ". Interpretation withheld until test limits are signed off.")
    # signed path: trend words only when the signed threshold allows them
    hl = row.get("expected_half_life_h"); fall = row.get("rcv_fall_pct"); rise = row.get("rcv_rise_pct")
    ch = (vl - v0) / v0 * 100 if v0 else 0
    if hl and vl < v0: trend, kin = "Fell", f"at about the expected rate for {pts[0]['concept_id']}"
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
            f"<i>For the clinical team:</i> one patient, admission baseline, {rec} gap recorded, {inferred} inferred "
            f"(&gt;{limit_h:g} h), {n_unmapped} results unmapped, limits {e(row.get('status','?')).lower()}, mapping {mapping_ver}.")

def png_b64(fig):
    b = io.BytesIO(); fig.savefig(b, format="png"); plt.close(fig); return base64.b64encode(b.getvalue()).decode()

def build(text, out="gallery.html", mode="ward"):
    d, unmapped, bad = prepare(read_table(text))
    try: ver = subprocess.run(["git", "-C", str(HERE), "log", "-1", "--format=%h", "--", "mapping.csv", "units.csv", "limits.csv"],
                              capture_output=True, text=True).stdout.strip() or "uncommitted"
    except Exception: ver = "uncommitted"
    limits = pl.read_csv(HERE / "limits.csv")
    cards, checks = [], []
    for (patient, concept), s in d.group_by(["patient", "concept_id"], maintain_order=True):
        unit = s["map_unit"].drop_nulls()[0]
        nu = unmapped.filter(pl.col("patient") == patient).height + bad.filter(pl.col("patient") == patient).height
        row = limits.filter(pl.col("concept_id") == concept); lim = row["gap_limit_h"]
        if lim.is_empty(): raise SystemExit(f"No signed-off gap limit for {concept} in limits.csv")
        limit_h = float(lim[0]); from datetime import timedelta
        fig, runs, meas = draw(s, concept, unit, patient, nu, ver, timedelta(hours=limit_h), mode)
        checks.append((s, runs, fig))
        cards.append(f"<figure><img src='data:image/png;base64,{png_b64(fig)}'><figcaption>"
                     f"{legend_text(concept, unit, s, runs, nu, ver, limit_h, row.row(0, named=True))}</figcaption></figure>")
    page = ("<!doctype html><meta charset=utf-8><title>figures</title><style>body{font:14px sans-serif;max-width:760px;"
            "margin:2em auto}figure{margin:0 0 3em}img{width:100%}figcaption{font-size:13px;line-height:1.4}</style>"
            f"<h1>Figures</h1><p>{len(cards)} figures. Single-patient charts: this file is the only copy; delete it when done.</p>"
            + "".join(cards))
    Path(out).write_text(page); return out, checks

if __name__ == "__main__":
    text = Path(sys.argv[1]).read_text() if len(sys.argv) > 1 else sys.stdin.read()
    print(build(text)[0])
