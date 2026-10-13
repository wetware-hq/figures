# Decisions

Why `figures` behaves the way it does. Each rule names the test that enforces it, or says **none**. Rules marked none are conventions only; that list is the to-do list.

## Drawing
- **No interpolation, ever.** A drawn line across a gap gets read as a measurement. Test: `test_rules` (4: no point inside an absence span).
- **Line breaks at every recorded absence.** Test: `test_rules` (1).
- **Inferred breaks are cosmetic only.** A break from a per-concept gap limit (`limits.csv`) never becomes an absence marker or gets "not measured" wording. Inferring meaning from a gap's shape is banned. Test: `test_inferred_break_not_recorded_gap`.
- **Every measured row is plotted; none silently dropped.** Test: `test_rules` (3).
- **Unmapped rows appear on the chart**, not just in metadata. Silent omission looks like a gap. Test: **none**.
- **One plot, two axes, no secondary axes, no title.** Test: `test_rules` (2), `test_no_title_and_anchored_age`.
- **A marker at every result**, so sampling density reads as dots thinning out. Test: **none**.
- **Unmeasured span shaded in full and labelled in words**, as `4 days (96 h) between results`, the same string on chart and legend. Shading never carries meaning without words. Test: **none**.
- **Hollow marker on an isolated last result**, labelled with its age. Test: **none**.

## Baseline and time
- **Baseline is the admission value.** A pre-illness value appears only as a second labelled reference line with date and source. "Best value this admission" is banned because it flatters. Test: **none**.
- **No relative time without its anchor.** Ages read "48 h before data as-at …". Test: `test_no_title_and_anchored_age`.
- **A result dated after the anchor refuses to render.** It is a clock or data error, not a wording problem. Test: `test_future_dated_result_refused`.
- **Derive, don't store** lag, gaps and calendar marks. Only the device clock offset is stored. Test: **none**.

## Meaning
- **Concept mapping and unit conversion come from versioned tables**, and every figure stamps the mapping version. Unversioned is a hard fail. Test: unit conversion in `test_rules`; version stamp **none**.
- **`gap_reason` defaults to `unknown`.** Weekends and public holidays may be marked from the calendar. `patient_declined` only from a recorded patient statement. Test: **none**.
- **Device and derivation recorded per value**; monitor-derived numbers say so. Test: **none**.

## Legends
- **Legends live in `legends.md`, not in the image.** Test: `test_png_has_no_legend_text`.
- **The image carries one capped footer line only**: synthetic, one patient, read with the bedside, interpretation withheld, figure and render ID. Additions go through the Director. Test: `test_png_has_no_legend_text`.
- **Legend shape: hand-back first, then interpretation, then alternative explanations; team stamps on a second, labelled line.** Truncation drops numbers, then kinetics; alternatives and the bedside hand-back never go. Test: **none**.
- **Interpret the analyte, never the patient.** "Marker plateaued", never "improving". Test: **none**.
- **"Fell" or "rose" only when the change clears that test's signed reference change value or expected decay** in `limits.csv`. While limits are DRAFT, the legend states values, dates and the gap, with no direction implied. Test: **none**.

## Privacy and files
- **One-patient (Class B) figures are never hashed and never stored with a points CSV.** They use a random render ID. Content hashes are for cohort (Class A) figures only. Test: **none**.
- **A legend and image with mismatched render IDs are refused.** Test: `test_mismatched_pair_refused`.
- **The HTML gallery is synthetic-only.** Real one-patient charts go to screen or print. Test: **none**.
- **Free text and waveforms are excluded from v0**, stated explicitly. Waveforms are biometric data. Test: **none**.
- **`figures` is a renderer, not a warehouse:** pasted, drawn, forgotten. Test: **none**.

## Known gap
`test_journal_and_test_copies` runs the journal build but asserts nothing, so the journal/test copy split is currently untested.
