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

def synopsis(s, runs, limit_h):
    """Rule-based, reproducible interpretation of the trend. No model; every sentence traceable to numbers."""
    pts = [p for r in runs for p in r]
    if len(pts) < 3: return "Too few measurements to describe a trend."
    v0, vl, t0, tl = pts[0]["v"], pts[-1]["v"], pts[0]["t"], pts[-1]["t"]
    ch = (vl - v0) / v0 * 100 if v0 else 0
    out = [f"Fell from {v0:g} to {vl:g} ({ch:+.0f}%) between {t0:%d %b} and {tl:%d %b}." if ch < -10 else
           f"Rose from {v0:g} to {vl:g} ({ch:+.0f}%) between {t0:%d %b} and {tl:%d %b}." if ch > 10 else
           f"Little change overall ({v0:g} to {vl:g}, {ch:+.0f}%)."]
    i_min = min(range(len(pts)), key=lambda i: pts[i]["v"])
    tail = pts[-4:]
    if len(tail) >= 3 and (max(p["v"] for p in tail) - min(p["v"] for p in tail)) <= 0.1 * max(abs(tail[-1]["v"]), 1):
        out.append(f"The last {len(tail)} results are within 10% of each other, a plateau rather than continued change.")
    if 0 < i_min < len(pts) - 1 and pts[-1]["v"] > pts[i_min]["v"] * 1.2:
        out.append(f"The lowest value was {pts[i_min]['v']:g} on {pts[i_min]['t']:%d %b}, and later results are higher.")
    gap = (tl - pts[-2]["t"]).total_seconds() / 3600
    if gap > limit_h:
        out.append(f"The latest value comes {gap:.0f} h after the one before it, so the trend between them is unobserved.")
    return " ".join(out)

def legend_text(concept, unit, s, runs, n_unmapped, mapping_ver, limit_h):
    meas = s.filter(pl.col("status") == "measured")
    rec = len(absences(s)); inferred = max(len(runs) - 1 - rec, 0)
    dev = ", ".join(sorted(set(f"{a} ({b})" for a, b in zip(meas["device"], meas["derivation"]))))
    base = runs[0][0] if runs else None
    e = html.escape
    return (f"<b>{e(synopsis(s, runs, limit_h))}</b><br>"
            f"<i>What:</i> {e(concept)} ({e(unit)}) for one patient, {meas['t'].min():%d %b} to {meas['t'].max():%d %b}. "
            f"One person's results, not evidence about anyone else.<br>"
            f"<i>Baseline:</i> admission value {base['v']:g} {e(unit)} on {base['t']:%d %b}.<br>"
            f"<i>Gaps:</i> {rec} recorded as not measured. The line also breaks after more than {limit_h:g} h without a result "
            f"({inferred} such breaks); that is the tool being cautious, not a recorded fact.<br>"
            f"<i>Not shown:</i> {n_unmapped} measurements, because their labels are not mapped yet.<br>"
            f"<i>Source:</i> {e(dev)}; mapping {mapping_ver}; synopsis is rule-based and describes the numbers, it is not a diagnosis.")

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
        lim = limits.filter(pl.col("concept_id") == concept)["max_gap_hours"]
        if lim.is_empty(): raise SystemExit(f"No signed-off gap limit for {concept} in limits.csv")
        limit_h = float(lim[0]); from datetime import timedelta
        fig, runs, meas = draw(s, concept, unit, patient, nu, ver, timedelta(hours=limit_h), mode)
        checks.append((s, runs, fig))
        cards.append(f"<figure><img src='data:image/png;base64,{png_b64(fig)}'><figcaption>"
                     f"{legend_text(concept, unit, s, runs, nu, ver, limit_h)}</figcaption></figure>")
    page = ("<!doctype html><meta charset=utf-8><title>figures</title><style>body{font:14px sans-serif;max-width:760px;"
            "margin:2em auto}figure{margin:0 0 3em}img{width:100%}figcaption{font-size:13px;line-height:1.4}</style>"
            f"<h1>Figures</h1><p>{len(cards)} figures. Single-patient charts: this file is the only copy; delete it when done.</p>"
            + "".join(cards))
    Path(out).write_text(page); return out, checks

if __name__ == "__main__":
    text = Path(sys.argv[1]).read_text() if len(sys.argv) > 1 else sys.stdin.read()
    print(build(text)[0])
