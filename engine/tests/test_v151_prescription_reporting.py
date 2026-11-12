"""Defect #64: a run could be overridden throughout while every artefact said it was not.

The cohort runner loaded one PrescriptionTable to write the run manifest and the engine loaded
another to do the lookups. Only the engine's instance ever saw a patient, so the manifest's
instance reported `n_patients_overridden: 0` and listed every entry under
`entries_not_matched_to_a_patient`.

That is exactly what the v1.5.0 sensitivity run's manifest says -- on a run where 54 of 116
patients demonstrably were overridden, which can be shown only by reading the recorded dose levels
back out of the per-patient harvests.

These tests fail on v1.5.0 and pass after the fix.
"""

from __future__ import annotations

import csv

import pytest

from dicom_io.prescription_table import (
    apply_to_plan_metadata,
    clear_prescription_table_cache,
    get_prescription_table,
)


@pytest.fixture(autouse=True)
def _clean_cache():
    clear_prescription_table_cache()
    yield
    clear_prescription_table_cache()


def _write_table(tmp_path, rows):
    p = tmp_path / "prescriptions.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["patient", "target_roi",
                                           "prescription_gy", "n_fractions"])
        w.writeheader()
        w.writerows(rows)
    return p


def test_the_same_table_object_is_returned_for_the_same_path(tmp_path):
    """#64: two instances meant the manifest described one that never did a lookup."""
    path = _write_table(tmp_path, [
        {"patient": "P1", "target_roi": "PTV70", "prescription_gy": 60.0, "n_fractions": 30},
    ])
    assert get_prescription_table(path) is get_prescription_table(path)
    assert get_prescription_table(str(path)) is get_prescription_table(path)


def test_the_manifest_reports_the_patients_that_were_actually_overridden(tmp_path):
    """The record the cohort runner writes must describe the object that did the lookups."""
    path = _write_table(tmp_path, [
        {"patient": "P1", "target_roi": "PTV70", "prescription_gy": 60.0, "n_fractions": 30},
        {"patient": "P2", "target_roi": "PTV70", "prescription_gy": 55.0, "n_fractions": 30},
    ])
    table = get_prescription_table(path)

    # Before anything is looked up, nothing is claimed as overridden.
    assert table.manifest_record()["n_patients_overridden"] == 0

    # One patient goes through the engine's seam.
    meta = {"prescription_dose_gy": 70.0, "n_fractions": 35, "dose_levels": []}
    out = apply_to_plan_metadata(meta, "P1", get_prescription_table(path))
    assert out["prescription_dose_gy"] == pytest.approx(60.0)

    # The SAME object now reports it, because there is only one object.
    rec = get_prescription_table(path).manifest_record()
    assert rec["n_patients_overridden"] == 1
    assert rec["patients_overridden"] == ["P1"]
    assert rec["entries_not_matched_to_a_patient"] == ["P2"]


def test_an_override_is_recorded_on_the_plan_metadata(tmp_path):
    """`prescription_source` is what a reader checks; it must say where the value came from."""
    path = _write_table(tmp_path, [
        {"patient": "P1", "target_roi": "PTV70", "prescription_gy": 60.0, "n_fractions": 30},
    ])
    meta = {"prescription_dose_gy": 70.0, "n_fractions": 35, "dose_levels": []}
    out = apply_to_plan_metadata(meta, "P1", get_prescription_table(path))
    assert out["prescription_source"] == "user_prescription_table"
    assert out["prescription_dose_gy_from_rtplan"] == pytest.approx(70.0)


def test_a_patient_absent_from_the_table_is_left_alone(tmp_path):
    path = _write_table(tmp_path, [
        {"patient": "P1", "target_roi": "PTV70", "prescription_gy": 60.0, "n_fractions": 30},
    ])
    meta = {"prescription_dose_gy": 70.0, "n_fractions": 35, "dose_levels": []}
    out = apply_to_plan_metadata(meta, "SOMEONE_ELSE", get_prescription_table(path))
    assert out["prescription_dose_gy"] == pytest.approx(70.0)
    assert "prescription_source" not in out
    assert get_prescription_table(path).manifest_record()["n_patients_overridden"] == 0


def test_the_tcp_row_carries_the_prescription_source():
    """#64: establishing application from the OUTPUT, not from the manifest.

    A row whose prescription came from the plan says so too, so the column is never ambiguous
    between "not overridden" and "column absent".
    """
    import pandas as pd

    from config.site_params import load_site_params
    from radiobiology import tcp_calculator as mod
    from radiobiology.tcp_calculator import TCPCalculator

    dvh = pd.DataFrame({"dose_gy": [35.0, 70.0], "volume_frac": [0.5, 0.5]})

    class _DvhResult:
        canonical_name = "PTV"
        quality_flag = "OK"
        dvh_object = object()

    original = mod.dvh_object_to_dataframe
    mod.dvh_object_to_dataframe = lambda _obj: dvh.copy()
    try:
        calc = TCPCalculator()
        plain = calc.compute_all(
            _DvhResult(),
            {"prescription_dose_gy": 70.0, "n_fractions": 35, "dose_per_fraction_gy": 2.0},
            load_site_params("HN"), target_type="PTV",
        )
        overridden = calc.compute_all(
            _DvhResult(),
            {"prescription_dose_gy": 60.0, "n_fractions": 30, "dose_per_fraction_gy": 2.0,
             "prescription_source": "user_prescription_table",
             "prescription_dose_gy_from_rtplan": 70.0},
            load_site_params("HN"), target_type="PTV",
        )
    finally:
        mod.dvh_object_to_dataframe = original

    assert plain["prescription_source"] == "rtplan"
    assert overridden["prescription_source"] == "user_prescription_table"
    assert overridden["prescription_dose_gy_from_rtplan"] == pytest.approx(70.0)
    assert overridden["total_dose_gy"] == pytest.approx(60.0)
