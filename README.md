# figures

Paste a raw flowsheet table in, get a figure gallery out. Figures follow Lancet/NEJM conventions; legends are stored separately, like a paper.

```
pip install -r requirements.txt
python figures.py fixtures/fixture_export.csv --as-at=2026-10-16T08:00:00   # or pipe/paste a TSV/CSV on stdin
python figures.py --verify gallery
```

Output in `gallery/`: `figure_N.png|svg|pdf` (image only, no title, no legend), `legends.md`, `index.html`.

## Rules
- One plot, two axes. No titles. House style in `default.mplstyle` (107 mm, 300 dpi, 8 pt sans, colour-blind-safe, text kept as text).
- No interpolation or downsampling. Gaps longer than the concept's limit are shaded and labelled, never recorded as absences.
- Legend is the synopsis, max two lines: line 1 "Read with the bedside…", line 2 "*For the clinical team:* …". It interprets the analyte, never the patient.
- Interpretation is withheld until the concept's row in `limits.csv` is SIGNED; until then legends state values, dates and intervals only.
- Results dated after the as-at anchor are refused. Legend and image are paired by a random render ID; `--verify` refuses mismatches.

## Data
`fixtures/` is synthetic. Do not commit real patient data; real trajectories go to screen or print only. Not for clinical use.
