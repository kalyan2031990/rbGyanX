"""End-to-end smoke test on generated synthetic DICOM-RT.

`test_data/dicom_input/` ships empty (DICOM is gitignored, deliberately), so the documented smoke test
used to complete with ``attempted: 0`` and look like a pass. This test generates the phantom cohort
first and then asserts the run actually processed it, so an empty input directory now fails loudly
instead of passing silently.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
GENERATOR = REPO / "scripts" / "make_synthetic_dicom_cohort.py"
RUNNER = REPO / "scripts" / "run_cohort.py"

pytest.importorskip("pydicom")
pytest.importorskip("dicompylercore")


@pytest.fixture(scope="module")
def synthetic_cohort(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("synthetic_dicom")
    r = subprocess.run([sys.executable, str(GENERATOR), "--out", str(d), "--patients", "2"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, f"generator failed:\n{r.stdout}\n{r.stderr}"
    dcm = list(d.rglob("*.dcm"))
    assert len(dcm) == 54, f"expected 54 DICOM files (2 x [24 CT + 3 RT]), got {len(dcm)}"
    return d


def test_generator_writes_a_complete_rt_study(synthetic_cohort: Path):
    """Each patient needs the full quartet, or the ingest layer has nothing to link."""
    import pydicom
    for patient in sorted(p for p in synthetic_cohort.iterdir() if p.is_dir()):
        mods = [str(pydicom.dcmread(f, stop_before_pixels=True, force=True).Modality)
                for f in patient.glob("*.dcm")]
        assert mods.count("CT") == 24, f"{patient.name}: {mods.count('CT')} CT slices"
        for m in ("RTSTRUCT", "RTPLAN", "RTDOSE"):
            assert mods.count(m) == 1, f"{patient.name}: {mods.count(m)} {m}"


def test_rtdose_carries_a_real_grid(synthetic_cohort: Path):
    """Guards the defect that made every DICOM DVH empty: RTDOSE PixelData IS the dose grid."""
    import numpy as np
    import pydicom
    rd = next(synthetic_cohort.rglob("RTDOSE.dcm"))
    ds = pydicom.dcmread(rd)
    assert ds.DoseUnits == "GY" and ds.DoseSummationType == "PLAN"
    assert int(ds.NumberOfFrames) == 24
    dose = ds.pixel_array * float(ds.DoseGridScaling)
    assert dose.max() > 40.0, f"peak dose {dose.max():.1f} Gy - grid did not decode"
    assert np.isfinite(dose).all()


def test_cohort_run_processes_the_synthetic_patients(synthetic_cohort: Path, tmp_path: Path):
    out = tmp_path / "out"
    r = subprocess.run(
        [sys.executable, str(RUNNER), "--input-root", str(synthetic_cohort),
         "--cohort", "SynthSmoke", "--output-root", str(out), "--input-kind", "dicom",
         "--validation", "ExternalValidation", "--mode", "basic", "--endpoint", "both",
         "--site", "HN"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, f"runner failed:\n{r.stdout}\n{r.stderr}"
    # the whole point: an empty input directory must not look like success
    assert "'attempted': 2" in r.stdout, f"expected 2 attempted, got:\n{r.stdout}"
    assert "'completed': 2" in r.stdout
    assert "'failed': 0" in r.stdout

    ntcp = list(out.rglob("ntcp_results.csv"))
    assert ntcp, "no ntcp_results.csv produced"
    d = pd.read_csv(ntcp[0])
    assert {"structure", "model", "ntcp"} <= set(d.columns)
    finite = d["ntcp"].dropna()
    assert len(finite) > 0, "every NTCP was NaN - the dose grid did not reach the models"
    assert ((finite >= 0) & (finite <= 1)).all(), "NTCP outside [0, 1]"
    assert finite.gt(0).any(), "all NTCP are zero - dose is not being read"
