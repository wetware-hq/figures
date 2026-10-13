# figures

> **Not approved for real patient data.** This is a research prototype tested on synthetic data only. Privacy and ethics approval, device-data access and the biometric-data review are pending, and whether it is a medical device under TGA software rules has not been assessed. It is not for clinical decision-making. "Formal environment" describes how software agents use it, not clinical readiness.

## Abstract
Results copied out of hospital record systems arrive as messy tables: mixed layouts, flags, comments in place of numbers, amended results and stray rows from other patients. `figures` turns one such paste into a clean time series and, optionally, a publication-style chart with a separate figure legend. It processes everything in memory and keeps nothing afterwards; for patients, nothing leaves and nothing is kept. Anything it cannot read with certainty is rejected and listed rather than guessed. On real data, software agents learn only that a chart exists, never what it shows.

## 1. Intended use
- **Users:** clinicians and researchers preparing charts of laboratory and bedside measurements; software agents acting on their behalf.
- **Inputs:** one table-like paste of results for one patient, as text (synthetic only), a local file or the clipboard.
- **Outputs:** a clean table of samples; for synthetic data, figure files (PNG, SVG, PDF) with legends stored separately in `legends.md`.
- **Out of scope:** storing data, combining pastes or patients, real-time monitoring, waveforms and clinical advice.

## 2. Data model
Each result is a **sample**: a time, a value and a status, which is measured, censored (for example `<5`, with the bound kept) or absent (with the reason, such as "haemolysed"). Samples belong to a **series** identified by test, unit, source and specimen. The patient identifier is used only to check that all rows belong to one person; it never labels a series and is never echoed. Samples are never interpolated, resampled or summarised.

## 3. Cleaning rules
- Accepted layouts: tab, comma, pipe or space-aligned columns; times down the rows or across the columns; oldest-first or newest-first.
- Flags such as `H` or `*` are removed, and a pasted reference range is never taken as the result.
- Of an amended pair, only the final result is kept. If the paste does not say which is final, both are rejected.
- Rejected, never guessed: dates that could be day-first or month-first, values without units, unknown labels, labels matching two tests.
- Refused outright: more than one patient, time running forwards then backwards within a series, series in different time orders, more than 50 series.
- Each rejection names the line, the field and the reason, never the line's contents.

## 4. Privacy model
Text input is accepted only when every patient identifier is a synthetic `SYNTH-` code. Any other text paste is refused with an instruction to report a privacy incident, because by then it has already been copied. This check is a tripwire, not a control: it proves the label, not the data. Real data enters only from a local file or the clipboard, stays in memory, is never written to disk and returns only counts, units and rejection reasons. The chart's "as at" time on real data comes from the machine's own clock and cannot be set.

## 5. Agent interface
`server.py` is a local tool server (Model Context Protocol, stdio); nothing is hosted.

| Action | Returns |
|---|---|
| `clean(text \| file \| clipboard, as_at?)` | handle, series counts and units, rejection counts; rows for synthetic data only |
| `rejects(handle)` | line, field and reason for each rejected line |
| `render(handle)` | file paths for synthetic data; real data is refused for now |

One session is one episode. Handles exist only in memory and end with the session. Every response is checked against a schema in `schemas/`, and every refusal carries a stable code such as `INTERLEAVED_TIME`. Identical input gives identical cleaned output.

## 6. Figures
There is one plot with two axes and no title. Shared style is set in `default.mplstyle`: 107 mm wide at 300 dpi, an 8 pt sans-serif font and colour-blind-safe colours. Gaps longer than the test's limit are shaded and labelled in words. The legend has at most two lines. It describes the test, not the patient. Its interpretation is withheld until that test's limits in `limits.csv` are signed off.

## 7. Evaluation
- `python evals/run.py`: regression cases checking outcomes, determinism and wording rules; runs in CI with `pytest`.
- `evals/READER_TEST.md`: a three-question test with people, run whenever the wording or look changes.
- Held-out cases are kept outside this repository. Until they exist, results show only that the tool does what it was built to do.

## 8. Known limitations
- Charts of real data cannot yet be shown on a ward screen.
- Not yet built: checking that synthetic data falls in 1937, keeping only known clinical columns, splitting a series when the test method changes, and a test for leftover temporary and print-spool files.
- A neighbour's row with plausible values and no identifier column cannot be detected. Every chart therefore says "identity not verified".

## Usage
```
pip install -r requirements.txt
python clean.py < fixtures/fixture_export.csv
python figures.py fixtures/fixture_export.csv --as-at=2026-10-16T08:00:00
python server.py
```
Design decisions and the test that enforces each one are in `DECISIONS.md`. MIT licence.
