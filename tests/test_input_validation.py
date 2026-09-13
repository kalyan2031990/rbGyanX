"""
A4 — input-validation robustness gate.

Malformed or incomplete input fails fast with a clear, actionable message instead of a
silent NaN / empty result. Covers all three input paths on synthetic data:
DVH text, DICOM RT, and missing target structures. (The generic clinical-CSV path is
covered in test_reusable_interfaces.py.)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dicom_io.dicom_reader import DicomPlanReader
from dicom_io.input_validation import (
    ensure_rtstruct_has_rois,
    ensure_targets_present,
)
from dicom_io.txt_dvh_reader import iter_dvh_text_files, parse_dvh_text_file
from tests.synthetic.dicom_rt_factory import SyntheticROI, build_rt_triple, save_dataset

# --------------------------------------------------------------------------- DVH text


def test_dvh_missing_directory_errors():
    with pytest.raises(FileNotFoundError, match="DVH directory not found"):
        iter_dvh_text_files(Path("does/not/exist/here"))


def test_dvh_empty_directory_errors(tmp_path):
    with pytest.raises(FileNotFoundError, match="No DVH files matching"):
        iter_dvh_text_files(tmp_path)


def test_dvh_glob_no_match_errors(tmp_path):
    (tmp_path / "present.txt").write_text("Structure: PTV\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="No DVH files matching"):
        iter_dvh_text_files(tmp_path, "*.dvh")


def test_dvh_no_data_rows_errors(tmp_path):
    p = tmp_path / "bad.txt"
    p.write_text("Patient ID: X\nStructure: PTV70\nno numeric rows here\n", encoding="utf-8")
    with pytest.raises(ValueError, match="No DVH data rows"):
        parse_dvh_text_file(p)


def test_dvh_zero_volume_errors(tmp_path):
    p = tmp_path / "zero.txt"
    p.write_text(
        "Structure: PTV70\nDose [cGy]  Volume [cm3]\n1000 0.0\n2000 0.0\n5000 0.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Zero differential volume"):
        parse_dvh_text_file(p)


# --------------------------------------------------------------------------- DICOM RT


def _write_folder(tmp_path, rt_struct, rt_dose, rt_plan=None) -> Path:
    d = tmp_path / "patient"
    d.mkdir()
    save_dataset(rt_struct, d / "rs.dcm")
    save_dataset(rt_dose, d / "rd.dcm")
    if rt_plan is not None:
        save_dataset(rt_plan, d / "rp.dcm")
    return d


def test_dicom_missing_folder_errors():
    with pytest.raises(FileNotFoundError, match="Patient folder not found"):
        DicomPlanReader().load_patient_dicom("no/such/folder/xyz")


def test_dicom_missing_modality_errors(tmp_path):
    rs, rd, _rp = build_rt_triple()
    folder = _write_folder(tmp_path, rs, rd)  # RT Plan omitted
    with pytest.raises(FileNotFoundError, match="Missing required DICOM modalities"):
        DicomPlanReader().load_patient_dicom(folder)


def test_dicom_empty_rtstruct_errors(tmp_path):
    rs, rd, rp = build_rt_triple(rois=[])  # structure set with zero ROIs
    folder = _write_folder(tmp_path, rs, rd, rp)
    with pytest.raises(ValueError, match="no ROIs"):
        DicomPlanReader().load_patient_dicom(folder)


# ------------------------------------------------------------------- missing structures


def test_ensure_rtstruct_has_rois_on_empty():
    rs, _rd, _rp = build_rt_triple(rois=[])
    with pytest.raises(ValueError, match="no ROIs"):
        ensure_rtstruct_has_rois(rs)


def test_ensure_targets_present_raises_when_only_oars():
    rois = [SyntheticROI("Larynx", "ORGAN", 18.0, 36.0, 18.0, 36.0, 6.0, 21.0)]
    rs, _rd, _rp = build_rt_triple(rois=rois)
    with pytest.raises(ValueError, match="no target volume"):
        ensure_targets_present(rs)


def test_ensure_targets_present_ok_with_ptv():
    rs, _rd, _rp = build_rt_triple()  # default ROIs include PTV70
    targets = ensure_targets_present(rs)
    assert any(t["canonical"] == "PTV" for t in targets)
