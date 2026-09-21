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
4000  100.0
5000  80.0
6000  50.0
7000  10.0
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


def test_multi_structure_survives_with_preserve_canonical_false(tmp_path: Path) -> None:
    """Regression for the SPARK canonical-key collision (B.1): before this fix,
    preserve_canonical=False routed a multi-structure file straight to the single-structure
    reader, which has no per-block boundary reset -- it silently kept only the last structure's
    name over dose/volume rows accumulated across ALL structures, discarding the other 5 (a real
    cohort had 6 ROIs per file). Bladder/Rectum/PTV here all coerce to canonical "PTV" when
    preserve_canonical=False (matching collect_txt_tcp's target-coercion default), which is
    exactly the collision that used to collapse -- so this must return all three, each with its
    own correct, distinct value, not one contaminated survivor."""
    content = """\
Patient ID           : MS-002
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
    path = tmp_path / "MS-002_Planned_DVH.txt"
    path.write_text(content, encoding="utf-8")

    from rbgyanx_engine.pipeline import _read_txt_structures

    results = _read_txt_structures(path, 2.0, False)  # the SPARK cohort's actual configuration
    assert len(results) == 3, "one or more colliding structures was silently discarded"
    assert {r.canonical_name for r in results} == {"PTV"}  # all coerced -- this IS the collision
    by_raw = {r.raw_name: r for r in results}
    assert {"Bladder", "Rectum", "PTV"} == set(by_raw)
    assert by_raw["Bladder"].dmean_gy == pytest.approx(7.0)  # not contaminated by the other blocks
    assert by_raw["Rectum"].dmean_gy == pytest.approx(10.0)
    assert by_raw["PTV"].dmean_gy == pytest.approx(36.9)


def test_multi_structure_falls_back_to_single(tmp_path: Path) -> None:
    content = """\
Patient ID           : S-1
Structure: PTV
Dose [cGy]  Volume [cm³]
6000 100.0
7000 50.0
"""
    path = tmp_path / "single.txt"
    path.write_text(content, encoding="utf-8")
    results = parse_multi_structure_dvh_text(path)
    assert len(results) == 1
    assert results[0].canonical_name == "PTV"
