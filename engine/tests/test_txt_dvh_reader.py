"""Tests for TPS DVH text reader."""

from pathlib import Path

import numpy as np
import pytest

from dicom_io.txt_dvh_reader import parse_dvh_text_file


def test_parse_minimal_cumulative_dvh(tmp_path: Path) -> None:
    content = """\
Patient ID           : TEST-001
Prescribed dose [cGy]: 7000.0
Mean Dose [cGy]: 7100.0
Structure: PTV70

Dose [cGy]  Structure Volume [cm³]
7000  100.0
6000  95.0
5000  80.0
4000  50.0
"""
    path = tmp_path / "TEST-001_dvh.txt"
    path.write_text(content, encoding="utf-8")
    result = parse_dvh_text_file(path)
    assert result.patient_id == "TEST-001"
    assert result.canonical_name == "PTV"
    assert result.plan_metadata["prescription_dose_gy"] == pytest.approx(70.0)
    assert len(result.dvh_object._df) >= 2
    assert np.isclose(result.dvh_object._df["volume_frac"].sum(), 1.0)
