"""Each test names the DECISIONS.md rule it enforces."""
import os, tempfile, pytest
from pathlib import Path
from clean import clean, from_file, to_parquet, parse_value, parse_time, Refused, TRIPWIRE

H = "patient\tlabel\ttime\tresult\tunit\tstatus\tsource\n"
def paste(*rows, pid="SYNTH-001"):
    return H + "\n".join(f"{pid}\t" + r for r in rows)

def test_censored_keeps_bound():
    assert parse_value("<5") == (5.0, "censored", "<")
    r = clean(paste("CRP\t1937-10-01 08:00\t<5\tmg/L\tfinal\tlab"))
    assert r.rows["status"][0] == "censored" and r.rows["bound"][0] == "<"

def test_lab_comment_becomes_absence_with_reason():
    r = clean(paste("CRP\t1937-10-01 08:00\tHaemolysed\t\tfinal\tlab"))
    assert r.rows["status"][0] == "absent" and r.rows["gap_reason"][0] == "haemolysed"

def test_flag_and_range_stripped_never_taken_as_result():
    assert parse_value("4.2 H (3.5-5.2)")[:2] == (4.2, "measured")
    assert parse_value("*36")[:2] == (36.0, "measured")
    assert parse_value("3.5-5.2")[1] == "reject"

def test_amended_keeps_final_unclear_rejects_both():
    r = clean(paste("CRP\t1937-10-01 08:00\t50\tmg/L\tpreliminary\tlab",
                    "CRP\t1937-10-01 08:00\t55\tmg/L\tcorrected\tlab"))
    assert r.rows["value"].to_list() == [55.0]
    r = clean(paste("CRP\t1937-10-01 08:00\t50\tmg/L\t\tlab", "CRP\t1937-10-01 08:00\t55\tmg/L\t\tlab"))
    assert r.rows.height == 0 and len(r.rejects) == 2

def test_same_time_two_sources_are_two_series_not_a_refusal():
    r = clean(paste("CRP\t1937-10-01 08:00\t50\tmg/L\tfinal\tlab", "CRP\t1937-10-01 08:00\t58\tmg/L\tfinal\tpoc"))
    assert r.rows.height == 2

def test_ambiguous_date_unit_and_label_rejected_not_guessed():
    assert parse_time("03/04/2026")[1] == "ambiguous day/month order"
    assert parse_time("13/04/2026")[0].month == 4
    r = clean(paste("CRP\t03/04/2026\t5\tmg/L\tfinal\tlab", "CRP\t1937-10-01 08:00\t5\t\tfinal\tlab",
                    "Nurse wellbeing score\t1937-10-01 08:00\t5\tpts\tfinal\tlab"))
    assert r.rows.height == 0 and {f for _, f, _ in r.rejects} == {"time", "unit", "label"}

def test_rejects_name_field_never_echo_line():
    r = clean(paste("CRP\t1937-10-01 08:00\tgarbage-value\tmg/L\tfinal\tlab"))
    assert all(len(x) == 3 and "garbage" not in x[2] for x in r.rejects)

def test_reversed_paste_passes():
    r = clean(paste("CRP\t1937-10-03 08:00\t60\tmg/L\tfinal\tlab", "CRP\t1937-10-02 08:00\t90\tmg/L\tfinal\tlab",
                    "CRP\t1937-10-01 08:00\t180\tmg/L\tfinal\tlab"))
    assert r.order == "newest-first" and r.rows.height == 3

def test_interleaved_refused():
    with pytest.raises(Refused, match="forwards then backwards"):
        clean(paste("CRP\t1937-10-01 08:00\t1\tmg/L\tfinal\tlab", "CRP\t1937-10-03 08:00\t2\tmg/L\tfinal\tlab",
                    "CRP\t1937-10-02 08:00\t3\tmg/L\tfinal\tlab"))

def test_mixed_order_across_series_refused():
    with pytest.raises(Refused, match="different time orders"):
        clean(paste("CRP\t1937-10-01 08:00\t1\tmg/L\tfinal\tlab", "CRP\t1937-10-02 08:00\t2\tmg/L\tfinal\tlab",
                    "Lactate\t1937-10-02 08:00\t2\tmmol/L\tfinal\tlab", "Lactate\t1937-10-01 08:00\t1\tmmol/L\tfinal\tlab"))

def test_more_than_one_patient_refused():
    with pytest.raises(Refused, match="more than one patient"):
        clean(H + "SYNTH-001\tCRP\t1937-10-01 08:00\t1\tmg/L\tfinal\tlab\nSYNTH-002\tCRP\t1937-10-02 08:00\t1\tmg/L\tfinal\tlab")

def test_text_path_refuses_unprovable_with_incident_message():
    with pytest.raises(Refused) as e:
        clean(paste("CRP\t1937-10-01 08:00\t1\tmg/L\tfinal\tlab", pid="MRN123456"))
    assert str(e.value) == TRIPWIRE
    with pytest.raises(Refused):
        clean("label\ttime\tresult\tunit\nCRP\t1937-10-01 08:00\t1\tmg/L")   # no identifier: not provable

def test_real_data_summary_has_no_values_or_times():
    with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False) as f:
        f.write("label\ttime\tresult\tunit\nCRP\t1937-10-01 08:00\t180\tmg/L\nCRP\t1937-10-02 08:00\t140\tmg/L")
    r = from_file(f.name); os.unlink(f.name)
    s = str(r.summary())
    assert "180" not in s and "1937" not in s and "rows" not in r.summary()
    assert r.summary()["identity"] == "not verified"

def test_real_data_never_written_to_disk(tmp_path):
    p = tmp_path / "x.tsv"; p.write_text("label\ttime\tresult\tunit\nCRP\t1937-10-01 08:00\t1\tmg/L")
    r = from_file(p)
    with pytest.raises(Refused):
        to_parquet(r, tmp_path / "out.parquet")
    assert not (tmp_path / "out.parquet").exists()

def test_wide_paste_times_across_columns():
    r = clean("patient\tlabel\tunit\t1937-10-01 08:00\t1937-10-02 08:00\nSYNTH-001\tCRP\tmg/L\t180\t140")
    assert r.rows["value"].to_list() == [180.0, 140.0]

def test_unit_conversion_and_fixture_roundtrip():
    r = clean(paste("CRP (ward 7 panel)\t1937-10-01 08:00\t3.9\tmg/dL\tfinal\tlab"))
    assert r.rows["value"][0] == pytest.approx(39) and r.rows["unit"][0] == "mg/L"
    fx = clean((Path(__file__).parent / "fixtures" / "fixture_export.csv").read_text())
    assert fx.synthetic and fx.rows.height > 0
