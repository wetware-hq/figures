# figures

> **Not approved for real patient data.** This is a research prototype tested on synthetic data only. Privacy and ethics approval, device-data access, and the biometric-data review are all still pending. "Formal environment" describes how agents interact with it, not clinical readiness. Not a medical device; not for clinical decision-making. Whether it falls under the TGA's software-as-a-medical-device rules has not been assessed.

A data clean room for EMR flowsheets: messy table-like pastes in, clean structured time-series data out, ready for graphing and parsing. Precisely, **zero-retention local processing**. For patients: *nothing leaves and nothing is kept.*

## Clean
```
python clean.py < fixtures/fixture_export.csv   # text path: provably synthetic only (SYNTH-### ids)
python clean.py --file export.tsv               # real data: local file on the ward machine
python clean.py --clipboard                     # real data: clipboard on the ward machine
```
Output is one long table: concept, time, value, unit, status (measured / censored / absent), bound, gap reason, result status, source, specimen. Real data stays in memory: agents get counts, units and reject reasons only, and nothing is written to disk. Ambiguous dates, missing units, unmapped or doubly mapped labels and unclear amended results are rejected, never guessed.

## Agent environment
`server.py` is a local MCP tool server (stdio) over `env.py`. An episode is one session; actions are `clean`, `rejects`, `render`; every observation validates against `schemas/*.json`, and every refusal carries a stable code (`env.ERRORS`). Handles live in memory and die with the session. `clean` is deterministic; the render ID is random and excluded. The as-at clock is settable on synthetic data only. Real-data `render` is display-only on the ward machine and returns nothing.

Evaluation: `python evals/run.py` (regression tests, runs in CI; held-out evaluation cases are kept outside the repo) and `evals/READER_TEST.md` (people tier, run when look or wording changes).

## Render
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
