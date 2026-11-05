"""An optional per-patient prescription table, and the guards on it (defect #60).

The engine takes one prescription per plan from the RT Plan. That is wrong whenever an archive
writes a nominal value into every plan while the real per-patient prescription lives elsewhere, and
it is not cosmetic: `radiobiology/tcp_calculator.py` computes TCP's EQD2 and BED from the
prescription directly, and the prescription-normalised plan-quality metrics (V95/V100 coverage,
conformity, gradient index) are scaled by it. A wrong prescription changes reported numbers without
changing any dose.

Nothing here is specific to any dataset: the table is a four-column CSV the user supplies, it is
optional, a patient absent from it keeps the RT Plan value, and the run manifest records which
patients were overridden.

These tests fail on v1.4.0, where `engine/dicom_io/prescription_table.py` does not exist.
"""

from __future__ import annotations

import math

import pytest

from dicom_io.prescription_table import (
    PrescriptionTableError,
    apply_to_plan_metadata,
    load_prescription_table,
)

HEADER = "patient,target_roi,prescription_gy,n_fractions\n"


def _table(tmp_path, body: str, name: str = "rx.csv"):
    p = tmp_path / name
    p.write_text(HEADER + body, encoding="utf-8")
    return p


# --------------------------------------------------------------------------- loading


def test_a_valid_table_loads(tmp_path):
    t = load_prescription_table(_table(tmp_path, "PT-1,PTV70,70,35\nPT-2,PTVHigh,60,35\n"))
    assert len(t) == 2
    assert t.entries["PT-2"].prescription_gy == 60.0
    assert t.entries["PT-2"].n_fractions == 35
    assert t.entries["PT-2"].dose_per_fraction_gy == pytest.approx(60.0 / 35)


def test_blank_target_roi_is_allowed_and_recorded(tmp_path):
    """Blank means 'the plan's named target' -- a legitimate statement, not missing data."""
    t = load_prescription_table(_table(tmp_path, "PT-1,,70,35\n"))
    assert t.entries["PT-1"].target_roi == ""


def test_a_missing_column_is_refused(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("patient,prescription_gy,n_fractions\nPT-1,70,35\n", encoding="utf-8")
    with pytest.raises(PrescriptionTableError, match="missing column"):
        load_prescription_table(p)


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(PrescriptionTableError, match="not found"):
        load_prescription_table(tmp_path / "nope.csv")


def test_a_header_with_no_rows_is_refused(tmp_path):
    with pytest.raises(PrescriptionTableError, match="no rows"):
        load_prescription_table(_table(tmp_path, ""))


def test_a_duplicate_patient_is_refused(tmp_path):
    """Two prescriptions for one patient has no defensible resolution, so it is not guessed."""
    with pytest.raises(PrescriptionTableError, match="more than once"):
        load_prescription_table(_table(tmp_path, "PT-1,PTV70,70,35\nPT-1,PTV70,60,35\n"))


@pytest.mark.parametrize("dose", ["0.5", "500", "nan", "seventy"])
def test_an_implausible_or_non_numeric_dose_is_refused(tmp_path, dose: str):
    """A unit error here would change TCP silently, so the range is a guard, not a formality."""
    with pytest.raises(PrescriptionTableError):
        load_prescription_table(_table(tmp_path, f"PT-1,PTV70,{dose},35\n"))


@pytest.mark.parametrize("nfrac", ["0", "-5", "900", "many"])
def test_an_implausible_fraction_count_is_refused(tmp_path, nfrac: str):
    with pytest.raises(PrescriptionTableError):
        load_prescription_table(_table(tmp_path, f"PT-1,PTV70,70,{nfrac}\n"))


def test_an_empty_patient_identifier_is_refused(tmp_path):
    with pytest.raises(PrescriptionTableError, match="empty patient"):
        load_prescription_table(_table(tmp_path, ",PTV70,70,35\n"))


# --------------------------------------------------------------------------- applying


def _plan_meta():
    return {"prescription_dose_gy": 70.0, "n_fractions": 35, "approval_status": "UNAPPROVED"}


def test_a_listed_patient_is_overridden_and_the_plan_value_kept(tmp_path):
    t = load_prescription_table(_table(tmp_path, "PT-1,PTVHigh,60,35\n"))
    out = apply_to_plan_metadata(_plan_meta(), "PT-1", t)
    assert out["prescription_dose_gy"] == 60.0
    assert out["dose_per_fraction_gy"] == pytest.approx(60.0 / 35)
    assert out["prescription_source"] == "user_prescription_table"
    assert out["prescription_target_roi"] == "PTVHigh"
    # The plan's own value is never lost.
    assert out["prescription_dose_gy_from_rtplan"] == 70.0
    assert out["n_fractions_from_rtplan"] == 35


def test_an_unlisted_patient_keeps_the_rtplan_value(tmp_path):
    t = load_prescription_table(_table(tmp_path, "PT-1,PTVHigh,60,35\n"))
    out = apply_to_plan_metadata(_plan_meta(), "PT-OTHER", t)
    assert out["prescription_dose_gy"] == 70.0
    assert "prescription_source" not in out


def test_no_table_changes_nothing():
    meta = _plan_meta()
    assert apply_to_plan_metadata(meta, "PT-1", None) == meta


def test_the_override_is_logged_with_both_values(tmp_path, caplog):
    t = load_prescription_table(_table(tmp_path, "PT-1,PTVHigh,60,35\n"))
    with caplog.at_level("INFO"):
        apply_to_plan_metadata(_plan_meta(), "PT-1", t)
    assert "70" in caplog.text and "60" in caplog.text
    assert "overridden" in caplog.text


# --------------------------------------------------------------------------- manifest


def test_the_manifest_record_names_who_was_overridden(tmp_path):
    t = load_prescription_table(_table(tmp_path, "PT-1,PTV70,70,35\nPT-2,PTVHigh,60,35\n"))
    apply_to_plan_metadata(_plan_meta(), "PT-2", t)
    rec = t.manifest_record()
    assert rec["entries"] == 2
    assert rec["patients_overridden"] == ["PT-2"]
    assert rec["n_patients_overridden"] == 1
    # An entry that matched no patient is a mistake worth seeing, not a silent no-op.
    assert rec["entries_not_matched_to_a_patient"] == ["PT-1"]
    assert rec["sha256"] and len(rec["sha256"]) == 64


def test_the_runner_config_accepts_a_table():
    from dataclasses import fields

    from rbgyanx_engine.cohort_runner import RunnerConfig

    assert any(f.name == "prescription_table" for f in fields(RunnerConfig))
    assert RunnerConfig.__dataclass_fields__["prescription_table"].default is None


# --------------------------------------------------------------------------- why it matters


def test_the_prescription_changes_the_eqd2_tcp_is_computed_from():
    """The point of the whole feature, asserted rather than assumed.

    TCP's EQD2 comes from the prescription and the fraction count, not from the target's measured
    dose, so substituting a lower prescription changes TCP for that patient.
    """
    from radiobiology import lq_model

    ab = 10.0
    eqd2_plan = lq_model.eqd2(70.0, 70.0 / 35, ab)
    eqd2_table = lq_model.eqd2(60.0, 60.0 / 35, ab)
    assert not math.isclose(eqd2_plan, eqd2_table, rel_tol=1e-6)
    assert eqd2_table < eqd2_plan
