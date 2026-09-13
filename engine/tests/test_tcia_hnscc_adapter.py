"""Tests for TCIA HNSCC adapter (mocked DICOM — no PHI)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from dicom_io.tcia_hnscc_adapter import adapt_patient_folder


def test_skip_patient_missing_rtdose(tmp_path: Path):
    rec = adapt_patient_folder(tmp_path / "empty_patient")
    assert rec.skipped
    assert "Missing" in rec.skip_reason or "not found" in rec.skip_reason.lower()


def test_adapter_yields_tg263_keyed_dvh(tmp_path: Path):
    mock_bundle = {
        "rt_plan": MagicMock(),
        "rt_dose": MagicMock(),
        "rt_struct": MagicMock(),
        "patient_id": "HN-001",
    }
    mock_oars = [{"roi_number": 1, "raw_name": "Parotid_L", "roi_type": "ORGAN"}]
    mock_dvh = MagicMock()
    mock_dvh.raw_name = "Parotid_L"
    mock_dvh.canonical_name = "Parotid_L"
    mock_dvh.dmean_gy = 30.0
    mock_dvh.dmax_gy = 60.0
    mock_dvh.dmin_gy = 5.0
    mock_dvh.total_volume_cc = 25.0
    mock_dvh.quality_flag = "OK"

    with patch("dicom_io.tcia_hnscc_adapter.DicomPlanReader") as Reader:
        inst = Reader.return_value
        inst.load_patient_dicom.return_value = mock_bundle
        inst.extract_plan_metadata.return_value = {
            "prescription_dose_gy": 70.0,
            "n_fractions": 35,
        }
        with patch("dicom_io.tcia_hnscc_adapter.get_oar_structures", return_value=mock_oars):
            with patch("dicom_io.tcia_hnscc_adapter.DVHExtractor") as Ext:
                Ext.return_value.extract_all_dvhs.return_value = {1: mock_dvh}
                rec = adapt_patient_folder(tmp_path)
    assert not rec.skipped
    assert "Parotid_L" in rec.dvh_by_tg263
    assert rec.plan_meta["prescription_dose_gy"] == 70.0
