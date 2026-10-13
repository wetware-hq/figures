# AGENTS.md: figures

Role: operate or modify a zero-retention cleaner and renderer for EMR flowsheet pastes. Research prototype; synthetic data only.

## Invariants (never violate; each has a test, see DECISIONS.md)
- Never pass real patient rows through your context. Text input = synthetic only (`SYNTH-` ids). Real data = `file`/`clipboard` on the local machine.
- If a user pastes real rows into chat: stop, do not repeat or process them, and tell them to report a privacy incident.
- Real data: observe counts, units and reject reasons only. Never request values, times or gap lengths.
- Never write real data to disk. Never set `as_at` on real data.
- Never guess: an ambiguous date, missing unit, unknown or duplicate label, or unclear amended result → reject.
- No interpolation, resampling, downsampling or best-value baselines. Absence ≠ zero.
- Patient id is used only for row-to-row comparison; never a series label; never echoed.
- Figures: one plot, x and y axes only, no title; legend ≤2 lines, stored separately; interpretation withheld unless the `limits.csv` row is SIGNED.
- Footer says "identity not verified" unless an identifier was present and every row matched it.
- Render ID is random; never derive it from data.

## Interface (server.py, MCP stdio)
- `clean(text|file|clipboard, as_at?)` → `{ok, handle, synthetic, identity, series[], rejects{}, rows?}`
- `rejects(handle)` → `{ok, rejects[{line, field, reason}]}`
- `render(handle)` → `{ok, shown, files[]}`; real data → `REAL_RENDER_LOCAL_DISPLAY_ONLY`
- Errors: `{ok:false, error, message}`. Branch on `error`; codes are listed in `env.ERRORS`. Handles are valid for the session only.

## Changing code
- Before commit: `pytest -q && python evals/run.py` must pass.
- New rule → add a test + a DECISIONS.md line naming it. Rule without test = say so.
- Changes to footer text, legend wording or figure look require BIO Director sign-off and a reader-test run (evals/READER_TEST.md).
- Do not add stored data, storage engines, query endpoints or new output fields for real data without explicit approval.
- Fixtures: synthetic only. Never commit real data.
