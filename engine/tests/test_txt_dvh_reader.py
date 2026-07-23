"""Tests for TPS DVH text reader."""

from pathlib import Path

import numpy as np
import pytest

from dicom_io.txt_dvh_reader import parse_dvh_text_file, parse_multi_structure_dvh_text


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


def test_parse_multi_structure_dvh(tmp_path: Path) -> None:
    # One Eclipse-style file holding several ROIs (Gy), each with its own block.
    content = """\
Patient ID           : MS-001
Prescribed dose [Gy]: 36.25

Structure: Bladder
Mean Dose [Gy]: 7.0
        Dose [Gy]   Ratio of Total Structure Volume [%]
0    100
5    60
10   20
15   0

Structure: Rectum
Mean Dose [Gy]: 10.0
        Dose [Gy]   Ratio of Total Structure Volume [%]
0    100
8    70
16   10
20   0

Structure: PTV
Mean Dose [Gy]: 36.9
        Dose [Gy]   Ratio of Total Structure Volume [%]
0    100
36   99
38   40
40   0
"""
    path = tmp_path / "MS-001_Planned_DVH.txt"
    path.write_text(content, encoding="utf-8")
    results = parse_multi_structure_dvh_text(path)

    by_canon = {r.canonical_name: r for r in results}
    assert {"Bladder", "Rectum", "PTV"}.issubset(by_canon)  # true per-ROI canonicals kept
    assert by_canon["Bladder"].dmean_gy == pytest.approx(7.0)  # per-structure header mean
    assert by_canon["Rectum"].dmean_gy == pytest.approx(10.0)
    assert by_canon["PTV"].dmean_gy == pytest.approx(36.9)
    assert all(r.patient_id == "MS-001" for r in results)  # shared preamble preserved


def test_multi_structure_falls_back_to_single(tmp_path: Path) -> None:
    content = """\
Patient ID           : S-1
Structure: PTV
Dose [cGy]  Volume [cm³]
7000 100.0
6000 50.0
"""
    path = tmp_path / "single.txt"
    path.write_text(content, encoding="utf-8")
    results = parse_multi_structure_dvh_text(path)
    assert len(results) == 1
    assert results[0].canonical_name == "PTV"
