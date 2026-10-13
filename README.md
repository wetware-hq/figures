# figures

**Overview.** figures is a local tool that turns one messy paste of hospital results into a clean time series and, for synthetic data, a publication-style chart with a separate legend. It processes everything in memory and keeps nothing. Anything it cannot read with certainty is rejected and listed, never guessed. Agent rules are in [AGENTS.md](AGENTS.md); each design rule and the test that enforces it are in [DECISIONS.md](DECISIONS.md).

> **Not approved for real patient data.** This is a research prototype tested on synthetic data only. Privacy and ethics approval, device-data access and the biometric-data review are pending. It is not a regulated medical device and is not for clinical decision-making; its regulatory status as medical-device software has not been assessed.

---

## Clinical abstract

Results copied out of a hospital record system rarely arrive clean. They come with flags such as `H`, comments like "haemolysed" in place of numbers, amended results, dates that could be read either way, and sometimes a row belonging to the patient in the next bed. A chart drawn from that paste can mislead without anyone noticing.

figures reads the paste once. It keeps only what it can read with certainty, then forgets everything. For a patient, nothing leaves and nothing is kept. On real data, an AI agent learns only that a chart exists, never what it shows. The clinician sees the chart; the agent sees counts.

Every result ends up in one of three states:

| Status | Example | Meaning |
|---|---|---|
| measured | `36` | a number with a unit |
| censored | `<5` | real result below or above a limit; the limit is kept |
| absent | `haemolysed` | no usable value; the reason is kept |

Rows that cannot be read safely are rejected, and the reason is listed without repeating the row's contents. Pastes that suggest two patients or two stitched-together charts are refused outright.

## Contract

| Slot | Direction | Type | Schema |
|---|---|---|---|
| **paste** | input | text (synthetic only), local file, or clipboard | one table, one patient |
| **series** | output | in memory; rows returned for synthetic data only | `schemas/clean.json` |
| **rejects** | output | line, field and reason | `schemas/rejects.json` |
| **gallery** | output | PNG, SVG and PDF plus `legends.md`, synthetic only | `schemas/render.json` |
| **error** | output | stable code plus message | `schemas/error.json` |

Agents call `clean`, `rejects` and `render` through `server.py`, a local Model Context Protocol server. Nothing is hosted. One session is one episode, and data handles end with it. Identical input gives identical cleaned output.

## Rules

- **No guessing.** Ambiguous dates (`03/04`), missing units, unknown labels, labels matching two tests, and amended results with no clear final version are rejected.
- **No invented data.** There is no interpolation, resampling or smoothing, and a missing result is never treated as zero.
- **Refused outright:** more than one patient; time running forwards then backwards; series in different time orders; more than 50 series.
- **Text input is synthetic only** (`SYNTH-` identifiers). Any other text paste is refused with an instruction to report a privacy incident. This is a tripwire, not a control: it proves the label, not the data.
- **Real data** enters only from a local file or the clipboard. It is never written to disk, and its "as at" time comes from the machine's own clock.
- **Charts** have one plot, two axes and no title, at 107 mm and 300 dpi in colour-blind-safe colours. The legend has at most two lines and is stored separately from the image. Interpretation is withheld until the test's limits are signed off. Every chart says "identity not verified" unless an identifier matched every row.
- The 1937 synthetic-date rule is not yet enforced by the tool. captaincook may call figures over MCP for synthetic data only, and only once that rule is enforced (see AGENTS.md).

## Pastes and refusals

Every paste goes through `clean.py`. Comma, tab, pipe, space and wide layouts are accepted. Pipe and wide pastes are accepted only when every column matches one known header. Anything else is refused, giving the row and column only. Row numbers are spreadsheet style: the file's own line numbers, with the header as row 1, so the first data row is row 2 (blank lines still count). A header problem says "row 1". Swapped time and value columns are caught.

- Semicolons: "Refused: semicolon-separated pastes aren't supported. Use commas or tabs." The refusal gives the first row with a semicolon.
- No usable rows: "Refused: no rows in the expected layout were found. Nothing was saved."
- A bad row: "Refused: row 4 doesn't match the expected layout."

A refusal shows the row number, the error type and the code line. It never shows pasted text or a traceback.

## Chart markers

| Marker | Legend |
|---|---|
| ▼ | "▼ below the test's limit (<5). The real value is lower than shown." |
| ▲ | "▲ above the test's limit (>90). The real value is higher than shown." |
| gap | "Gap: a result was recorded here but couldn't be read." |
| ✕ | "✕ Not done: no test was done at this time." |

A count line sits above the chart, for example: "3 rows couldn't be read and aren't shown: 1 is marked as a gap, 1 has no readable time, 1 has a test name we didn't recognise (row 7)." Each part appears only when it isn't zero, singular or plural matches the number, and the parts add up to the total.

A test missing from `limits.csv` is charted without a normal range and flagged: "Flag: no normal range on file for the test on row 4. It's charted without one." It is never shown as normal.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q && python evals/run.py
python clean.py < fixtures/fixture_export.csv
python figures.py fixtures/fixture_export.csv --as-at=1937-10-16T08:00:00
python server.py
```

## Evaluation

`evals/run.py` runs regression cases for outcomes, determinism and wording. `evals/READER_TEST.md` is a three-question test with people, run whenever the wording or look changes. Held-out cases use invented people and are kept outside this repository. Results are reported as counts, never rates. Held-out runs go through a version-checked runner outside the repo that logs the commit.

## Roadmap

1. **Clean and render** (v0.2, this repo).
2. Ship blockers: synthetic dates in 1937, keep only known clinical columns, split a series when the test method changes, no leftover temp or print-spool files.
3. Real-data charts shown on the ward screen only.
4. A warehouse, as a separate proposal: cohort rows only, query budgets, row-level read permissions, and a query log a patient can read.

## License

MIT, see [LICENSE](LICENSE).
