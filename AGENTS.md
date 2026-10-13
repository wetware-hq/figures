---
schema: wetware.agent.v1
resource: figures
version: 0.2.0
capabilities: [clean, rejects, render]
inputs:
  paste: {type: text|file|clipboard, constraint: "text = synthetic only"}
outputs:
  series: {type: memory, schema: schemas/clean.json}
  rejects: {type: list, schema: schemas/rejects.json}
  gallery: {type: directory, schema: schemas/render.json, constraint: synthetic only}
server: {transport: mcp-stdio, entrypoint: server.py}
---

# Agent contract

Normative rules for agents that operate or modify figures. Wording uses RFC 2119: **MUST**, **MUST NOT**, **SHOULD**. Not approved for real patient data.

## Data handling

1. Real patient rows **MUST NOT** enter agent context. Text input **MUST** carry only `SYNTH-` identifiers. Real data **MUST** come from `file` or `clipboard` on the local machine.
2. If a user pastes real rows into chat, the agent **MUST** stop, **MUST NOT** repeat or process them, and **MUST** tell the user to report a privacy incident.
3. On real data, agents **MUST** observe only counts, units and reject reasons. They **MUST NOT** request values, times or gap lengths.
4. Real data **MUST NOT** be written to disk. `as_at` **MUST NOT** be set on real data.
5. The patient identifier is used only for row-to-row comparison. It **MUST NOT** label a series or appear in any output.

## Interface

```
clean(text|file|clipboard, as_at?) → {ok, handle, synthetic, identity, series[], rejects{}, rows?}
rejects(handle)                    → {ok, rejects[{line, field, reason}]}
render(handle)                     → {ok, shown, files[]}
error                              → {ok: false, error, message}
```

Agents **MUST** branch on `error` codes (`env.ERRORS`), not on message text. Handles are valid for one session.

## Cleaning order

1. Split columns (tab, pipe, comma, then two or more spaces); recognise headers; melt times across columns into rows.
2. Refuse: `NOT_PROVABLY_SYNTHETIC`, `MULTIPLE_PATIENTS`, `NO_REQUIRED_COLUMN`, `EMPTY_INPUT`.
3. For each row, reject: unmapped or doubly mapped label → ambiguous or impossible date → unreadable value → missing unit → no unit conversion.
4. Values: comment → `absent` with reason; `<x`/`>x` → `censored` with bound; strip flags; never take a reference range as the result.
5. Refuse: `TOO_MANY_SERIES` (>50), `INTERLEAVED_TIME`, `MIXED_TIME_ORDER`. A consistently newest-first paste is accepted.
6. Amended results: keep the one marked final; if none or several, reject all of them.

## Figures

- One plot, x and y axes only, no title, house style `default.mplstyle`.
- Legend: at most two lines, stored separately from the image, describing the test and not the patient. No direction words unless the `limits.csv` row is SIGNED.
- No interpolation, resampling, downsampling or best-value baseline.
- The footer **MUST** read "identity not verified" unless an identifier matched every row.
- The render ID **MUST** be random and **MUST NOT** be derived from data.

## Changing code

- `pytest -q && python evals/run.py` **MUST** pass before commit.
- Every new rule **MUST** get a test and a `DECISIONS.md` line naming that test.
- Changes to footer text, legend wording or chart look **MUST** have BIO Director sign-off and a reader-test run.
- Fixtures **MUST** be synthetic.

## Out of scope

- Storage, warehouses, query endpoints, or combining pastes or patients
- Hosted services or vendor APIs
- Real-data file output and clinical advice
