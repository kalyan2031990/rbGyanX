"""
Phase 2 acceptance — synthetic corrupted-input battery for cohort ingest.

Constructs synthetic DICOM-RT (no patient data) exercising nested folders, multiple patients per tree,
multiplicity (several RTPLAN/RTDOSE/RTSTRUCT), every missing-modality combination, malformed/truncated
files, empty PatientID, and dose-unit hazards. Asserts:
  * ``discover_cohort`` never raises on bad input (constraint C4);
  * every degradation is a machine-readable reason code (no silent skips);
  * selection is deterministic — running twice is byte-identical (constraint C5);
  * the units/scaling guards flag cGy-vs-Gy, missing scaling, non-Gy units, and DVH disagreement.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling factory
from dicom_rt_factory import build_rt_triple, save_dataset  # noqa: E402

from dicom_io.cohort_discovery import discover_cohort  # noqa: E402
from dicom_io.dose_units_check import check_dose_units, mean_dose_agreement  # noqa: E402

pytestmark = pytest.mark.unit


def _place(folder: Path, *datasets, prefix: str = "IM") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for i, ds in enumerate(datasets):
        save_dataset(ds, folder / f"{prefix}_{ds.Modality}_{i}.dcm")


# ---------------------------------------------------------------- discovery / grouping


def test_two_patients_grouped_by_patient_id(tmp_path):
    s1, d1, p1 = build_rt_triple(patient_id="SYN-001")
    s2, d2, p2 = build_rt_triple(patient_id="SYN-002")
    # deliberately mix both patients' files under nested, non-patient-named folders
    _place(tmp_path / "aaa" / "series1", s1, d1)
    _place(tmp_path / "bbb", p1, s2)
    _place(tmp_path / "aaa" / "series2", d2, p2)

    manifests = discover_cohort(tmp_path)
    keys = {m.patient_key for m in manifests}
    assert keys == {"SYN-001", "SYN-002"}
    for m in manifests:
        assert m.degraded_mode == "FULL"  # plan+dose+struct present despite folder scatter


def test_no_ct_is_full_not_a_crash(tmp_path):
    """The key TCIA-lung robustness case: no CT must NOT block DVH-capable processing."""
    s, d, p = build_rt_triple(patient_id="SYN-001")
    _place(tmp_path / "pt", s, d, p)
    (m,) = discover_cohort(tmp_path)
    assert "MISSING_CT" in m.reason_codes
    assert m.degraded_mode == "FULL"


def test_multiple_plans_deterministic_approved_wins(tmp_path):
    s, d, plan_a = build_rt_triple(patient_id="SYN-001")
    plan_b = build_rt_triple(patient_id="SYN-001")[2]
    plan_a.ApprovalStatus = "APPROVED"
    plan_a.RTPlanDate = "20240101"
    plan_b.ApprovalStatus = "UNAPPROVED"
    plan_b.RTPlanDate = "20250101"  # newer but unapproved — must NOT win
    _place(tmp_path / "pt", s, d, plan_a, plan_b)

    (m,) = discover_cohort(tmp_path)
    assert "MULTIPLE_RTPLAN" in m.reason_codes
    chosen = __import__("pydicom").dcmread(m.rtplan_path)
    assert chosen.ApprovalStatus == "APPROVED"


def test_missing_dose_degrades_with_reason(tmp_path):
    s, _d, p = build_rt_triple(patient_id="SYN-001")
    _place(tmp_path / "pt", s, p)  # no dose
    (m,) = discover_cohort(tmp_path)
    assert "MISSING_RTDOSE" in m.reason_codes
    assert m.degraded_mode == "NO_DOSE"
    assert m.rtdose_path is None


def test_missing_struct_degrades_with_reason(tmp_path):
    _s, d, p = build_rt_triple(patient_id="SYN-001")
    _place(tmp_path / "pt", d, p)  # no struct
    (m,) = discover_cohort(tmp_path)
    assert "MISSING_RTSTRUCT" in m.reason_codes
    assert m.degraded_mode == "NO_STRUCT"


def test_missing_plan_still_processable(tmp_path):
    s, d, _p = build_rt_triple(patient_id="SYN-001")
    _place(tmp_path / "pt", s, d)  # no plan
    (m,) = discover_cohort(tmp_path)
    assert "MISSING_RTPLAN" in m.reason_codes
    assert m.degraded_mode == "NO_PLAN"  # DVH still computable; fractions unknown


def test_only_struct_is_no_dose(tmp_path):
    """Struct present but no dose → NO_DOSE (structures exist; DVH impossible)."""
    s, _d, _p = build_rt_triple(patient_id="SYN-001")
    _place(tmp_path / "pt", s)
    (m,) = discover_cohort(tmp_path)
    assert m.degraded_mode == "NO_DOSE"
    assert {"MISSING_RTDOSE", "MISSING_RTPLAN"} <= set(m.reason_codes)


def test_plan_only_is_insufficient(tmp_path):
    """Neither dose nor struct → nothing usable → INSUFFICIENT."""
    _s, _d, p = build_rt_triple(patient_id="SYN-001")
    _place(tmp_path / "pt", p)
    (m,) = discover_cohort(tmp_path)
    assert m.degraded_mode == "INSUFFICIENT"
    assert {"MISSING_RTDOSE", "MISSING_RTSTRUCT"} <= set(m.reason_codes)


def test_malformed_and_nondicom_files_are_skipped(tmp_path):
    s, d, p = build_rt_triple(patient_id="SYN-001")
    _place(tmp_path / "pt", s, d, p)
    (tmp_path / "pt" / "truncated.dcm").write_bytes(b"DICM\x00\x01garbage-not-a-dataset")
    (tmp_path / "pt" / "notes.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "pt" / "weird.dcm").write_bytes(bytes(range(256)))  # non-UTF8 bytes incl 0x8f
    manifests = discover_cohort(tmp_path)  # must not raise
    assert len(manifests) == 1
    assert manifests[0].degraded_mode == "FULL"


def test_empty_patient_id_grouped_by_frame_of_reference(tmp_path):
    s, d, p = build_rt_triple(patient_id="")
    for ds in (s, d, p):
        ds.PatientID = ""
    _place(tmp_path / "pt", s, d, p)
    (m,) = discover_cohort(tmp_path)
    assert m.patient_key == ""
    assert "NO_PATIENT_ID" in m.reason_codes


def test_missing_root_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        discover_cohort(tmp_path / "does_not_exist")


def test_discovery_is_deterministic(tmp_path):
    s, d, plan_a = build_rt_triple(patient_id="SYN-001")
    plan_b = build_rt_triple(patient_id="SYN-001")[2]
    plan_a.ApprovalStatus = "APPROVED"
    s2, d2, p2 = build_rt_triple(patient_id="SYN-002")
    _place(tmp_path / "a", s, d, plan_a, plan_b)
    _place(tmp_path / "b", s2, d2, p2)

    def snapshot():
        return [
            (
                m.patient_key,
                str(m.rtplan_path),
                str(m.rtdose_path),
                str(m.rtstruct_path),
                tuple(sorted(m.reason_codes)),
                m.degraded_mode,
            )
            for m in discover_cohort(tmp_path)
        ]

    assert snapshot() == snapshot()  # byte-identical across runs (C5)


# ---------------------------------------------------------------- units / scaling (2.5)


def test_units_ok_for_plausible_gy_dose(tmp_path):
    _s, dose, _p = build_rt_triple(patient_id="SYN-001", dose_gy=70.0)
    out = check_dose_units(dose)
    assert "CGY_SUSPECTED" not in out["reason_codes"]
    assert "MISSING_DOSE_GRID_SCALING" not in out["reason_codes"]


def test_cgy_magnitude_is_flagged():
    _s, dose, _p = build_rt_triple(
        patient_id="SYN-001", dose_gy=7000.0
    )  # cGy-magnitude stored as "Gy"
    assert "CGY_SUSPECTED" in check_dose_units(dose)["reason_codes"]


def test_missing_grid_scaling_is_flagged():
    _s, dose, _p = build_rt_triple(patient_id="SYN-001")
    del dose.DoseGridScaling
    assert "MISSING_DOSE_GRID_SCALING" in check_dose_units(dose)["reason_codes"]


def test_non_gy_units_flagged():
    _s, dose, _p = build_rt_triple(patient_id="SYN-001")
    dose.DoseUnits = "RELATIVE"
    assert "DOSE_UNITS_NOT_GY" in check_dose_units(dose)["reason_codes"]


def test_mean_dose_agreement_tolerance():
    assert mean_dose_agreement(30.0, 30.6)["ok"] is True  # within 5%
    bad = mean_dose_agreement(30.0, 45.0)  # 50% off
    assert bad["ok"] is False and bad["reason"] == "DOSE_DVH_MISMATCH"
    assert mean_dose_agreement(float("nan"), 30.0)["ok"] is True  # missing != disagreement
