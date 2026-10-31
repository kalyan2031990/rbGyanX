"""Tier A defect #18 — an arbitrary tie-break between plans is a refusal, not a choice.

Each test fails on v1.4.0 (``ffd69ef``) and passes after the fix.
"""

from __future__ import annotations

from pathlib import Path

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from dicom_io.cohort_discovery import discover_cohort

_FOR = generate_uid()


def _save_dataset(ds: Dataset, dst) -> None:
    """Write a Part-10 DICOM file on pydicom 2.x and 3.x alike.

    Same two-branch form as ``tests/synthetic/dicom_rt_factory.save_dataset``; duplicated rather
    than imported because ``tests`` is not an importable package from ``engine/tests`` under
    pytest's importlib mode. ``enforce_file_format`` alone fails on CI, which runs pydicom 2.
    """
    try:
        ds.save_as(dst, write_like_original=False)  # pydicom <3.0
    except TypeError:
        ds.save_as(dst, enforce_file_format=True)  # pydicom >=3.0


def _write_plan(
    folder: Path,
    *,
    label: str,
    approval: str = "UNAPPROVED",
    rx_gy: float = 70.0,
    n_frac: int = 35,
    plan_date: str = "20240101",
) -> Path:
    ds = Dataset()
    ds.PatientID = "SYN001"
    ds.Modality = "RTPLAN"
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.481.5"
    ds.SOPInstanceUID = generate_uid()
    ds.FrameOfReferenceUID = _FOR
    ds.RTPlanLabel = label
    ds.ApprovalStatus = approval
    ds.RTPlanDate = plan_date
    ds.RTPlanTime = "120000"

    ref = Dataset()
    ref.TargetPrescriptionDose = rx_gy
    ds.DoseReferenceSequence = [ref]
    fg = Dataset()
    fg.NumberOfFractionsPlanned = n_frac
    ds.FractionGroupSequence = [fg]

    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = ds.SOPClassUID
    meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta = meta

    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"RTPLAN_{label}.dcm"
    _save_dataset(ds, path)
    return path


def _write_struct_and_dose(folder: Path) -> None:
    for modality, sop_class in (
        ("RTSTRUCT", "1.2.840.10008.5.1.4.1.1.481.3"),
        ("RTDOSE", "1.2.840.10008.5.1.4.1.1.481.2"),
    ):
        ds = Dataset()
        ds.PatientID = "SYN001"
        ds.Modality = modality
        ds.SOPClassUID = sop_class
        ds.SOPInstanceUID = generate_uid()
        ds.FrameOfReferenceUID = _FOR
        meta = FileMetaDataset()
        meta.MediaStorageSOPClassUID = sop_class
        meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta = meta
        _save_dataset(ds, folder / f"{modality}.dcm")


def test_defect_18_two_indistinguishable_plans_are_refused(tmp_path: Path) -> None:
    """#18: both UNAPPROVED, same prescription, same date — only the UID order separated them."""
    folder = tmp_path / "SYN001"
    _write_plan(folder, label="PlanA")
    _write_plan(folder, label="PlanB")
    _write_struct_and_dose(folder)

    (m,) = discover_cohort(tmp_path)
    assert "AMBIGUOUS_PLAN_SELECTION" in m.reason_codes, m.reason_codes
    assert m.rtplan_path is None
    note = m.selection_notes["RTPLAN_AMBIGUITY"]
    assert "'PlanA'" in note and "'PlanB'" in note


def test_defect_18_a_named_plan_resolves_it(tmp_path: Path) -> None:
    folder = tmp_path / "SYN001"
    _write_plan(folder, label="PlanA")
    _write_plan(folder, label="PlanB")
    _write_struct_and_dose(folder)

    (m,) = discover_cohort(tmp_path, plan_label="PlanB")
    assert "AMBIGUOUS_PLAN_SELECTION" not in m.reason_codes, m.reason_codes
    assert m.rtplan_path is not None
    assert m.rtplan_path.name == "RTPLAN_PlanB.dcm"
    assert "PlanB" in m.selection_notes["RTPLAN"]


def test_defect_18_a_per_patient_override_resolves_it(tmp_path: Path) -> None:
    folder = tmp_path / "SYN001"
    _write_plan(folder, label="PlanA")
    _write_plan(folder, label="PlanB")
    _write_struct_and_dose(folder)

    (m,) = discover_cohort(tmp_path, plan_overrides={"SYN001": "PlanA"})
    assert "AMBIGUOUS_PLAN_SELECTION" not in m.reason_codes
    assert m.rtplan_path.name == "RTPLAN_PlanA.dcm"


def test_defect_18_an_approved_plan_is_not_ambiguous(tmp_path: Path) -> None:
    """Approval is a clinical fact, so it separates the two without an operator."""
    folder = tmp_path / "SYN001"
    _write_plan(folder, label="Draft")
    _write_plan(folder, label="Final", approval="APPROVED")
    _write_struct_and_dose(folder)

    (m,) = discover_cohort(tmp_path)
    assert "AMBIGUOUS_PLAN_SELECTION" not in m.reason_codes, m.reason_codes
    assert m.rtplan_path.name == "RTPLAN_Final.dcm"


def test_defect_18_a_different_prescription_is_not_ambiguous(tmp_path: Path) -> None:
    """A re-plan to a different dose is a different plan, and the latest one still wins."""
    folder = tmp_path / "SYN001"
    _write_plan(folder, label="Sixty", rx_gy=60.0, n_frac=30, plan_date="20240101")
    _write_plan(folder, label="Seventy", rx_gy=70.0, n_frac=35, plan_date="20240202")
    _write_struct_and_dose(folder)

    (m,) = discover_cohort(tmp_path)
    assert "AMBIGUOUS_PLAN_SELECTION" not in m.reason_codes, m.reason_codes
    assert m.rtplan_path.name == "RTPLAN_Seventy.dcm"


def test_defect_18_a_later_date_separates_two_unapproved_plans(tmp_path: Path) -> None:
    folder = tmp_path / "SYN001"
    _write_plan(folder, label="Early", plan_date="20240101")
    _write_plan(folder, label="Late", plan_date="20240303")
    _write_struct_and_dose(folder)

    (m,) = discover_cohort(tmp_path)
    assert "AMBIGUOUS_PLAN_SELECTION" not in m.reason_codes, m.reason_codes
    assert m.rtplan_path.name == "RTPLAN_Late.dcm"


def test_defect_18_a_single_plan_is_never_ambiguous(tmp_path: Path) -> None:
    folder = tmp_path / "SYN001"
    _write_plan(folder, label="Only")
    _write_struct_and_dose(folder)

    (m,) = discover_cohort(tmp_path)
    assert "AMBIGUOUS_PLAN_SELECTION" not in m.reason_codes
    assert "MULTIPLE_RTPLAN" not in m.reason_codes
    assert m.rtplan_path.name == "RTPLAN_Only.dcm"


def test_defect_18_a_third_clearly_worse_plan_does_not_create_ambiguity(tmp_path: Path) -> None:
    """Only the plans that tie with the winner count; an older one is simply not chosen."""
    folder = tmp_path / "SYN001"
    _write_plan(folder, label="Old", plan_date="20230101")
    _write_plan(folder, label="New", plan_date="20240303", approval="APPROVED")
    _write_struct_and_dose(folder)

    (m,) = discover_cohort(tmp_path)
    assert "AMBIGUOUS_PLAN_SELECTION" not in m.reason_codes, m.reason_codes
    assert m.rtplan_path.name == "RTPLAN_New.dcm"
