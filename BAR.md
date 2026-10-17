# figures — the bar

What a green means in figures, and what it does not. A green here is not the same assurance as a green in a sibling repo; read this before quoting one.

**Not a medical device; not approved for real patient data.** A pass means the checks behaved as signed on synthetic data, nothing more.

## The bar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q                       # the suite (runs in the venv)
python evals/run.py             # in-repo regression: outcomes, determinism, wording
python scripts/rulecheck.py     # rules register; no prose outside WORDING.md
python scripts/mutate.py        # mutation gate over safety_functions.toml
```

`pytest` green in the venv is figures' bar; `evals/run.py` and `rulecheck.py` are run alongside it, and `mutate.py` (with `mutate_rowcheck.py`) is the mutation gate. Before pushing, maintainers run `scripts/prepush.py`.

## What a green covers

- **No guessing, no invented data** — ambiguous dates, missing units, unknown or two-matching labels, and amended results with no clear final version are rejected; there is no interpolation, resampling or smoothing, and a missing result is never treated as zero (`test_rules`, `test_clean`, `test_rowcheck`).
- **Refusals** — more than one patient, time running forwards then backwards, mixed time orders and more than 50 series are refused; refusals give the row, field and code line only, never pasted text or a traceback (`test_clean`, `test_rules`).
- **Censored values** — `<X`/`>X` are drawn as marked limits, left out of trend lines, first/latest values and normal-range comparison, and never split a line into a gap.
- **Reproducibility** — identical input gives identical cleaned output (`test_generalisation`, eval determinism cases).
- **Clock discipline** — only `clock.py` reads the box clock (`test_clock`); a result dated after the as-at anchor refuses to render.
- **Wording from signed source** — `test_wording`, `test_wording_signed_source`, `test_signed_tests_read_signed_source`, `test_signing_header_count`, `test_no_duplicate_signed_ids`, and `test_prepush_answer_files` run here and pass.
- **Safety functions** — mutation-killed (`test_mutation_kills`, `test_safety_functions`, `test_safety_stamp`).
- **Jurisdiction scan** — `test_jurisdiction_scan.py` fails on any planted term in each category below, each on its own id.

The scan's category ids are not copied here: duplicating the registry would drift from it, and can trip the scan on an id that itself contains a scanned term. The authoritative list is the `[categories]` table in `jurisdiction_scan.toml`, and `test_bar.py` checks this bar points to it.

## What a green does NOT cover

- **Rules marked "Test: none" in `DECISIONS.md`.** Those are conventions only, not enforced by any test; that list is the to-do list, not something a green stands behind.
- **The 1937 synthetic-date rule.** Specified but **unbuilt** in the tool; host integrations that paste synthetic text must wait until it is enforced (README, AGENTS.md).
- **Held-out evaluation.** Held-out cases use invented people, are kept outside this repository, and run through a version-checked external runner reported as counts; a local green does not include them.
- **Live-model behaviour.** S05 and S07 were checked with a scripted stand-in, not a real AI model.
- **The mutation sweep and pre-push unless run.** `mutate.py` and `prepush.py` are separate gates; a `pytest` green alone does not include them.
- **Real data or clinical validity.** A green is a code check on synthetic data; figures makes no clinical decision and is not a medical device.

## Name guard

`test_bar.py` checks this bar names `jurisdiction_scan.toml` as the authoritative scan registry, rather than copying the category ids (a copy would drift from the registry and can trip the scan itself). The registry's own test (`test_each_category_planted_term_fails_on_its_own_id`) holds every category to one declared, planted id, so no scan check runs under a name the registry does not name.
