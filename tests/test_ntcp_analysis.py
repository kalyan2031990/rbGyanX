"""Test NTCP analysis workflow"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Defect #46 follow-up. These tests run `legacy/code3_ntcp_analysis_ml.py` in a subprocess, and that
# module imports seaborn, which lives in the `ml` extra. The CI core job installs only `.[dev]`, so
# the subprocess exits with ModuleNotFoundError there and the assertion on its return code fails.
# This is the `legacy` marker's declared purpose: the code under test is quarantined lineage code,
# retired and never imported by the engine, and a contributor should not have to install a plotting
# library to run the core suite in order to support it. The `full` job installs the extras and
# applies no marker filter, so these tests still run there -- the coverage moves, it does not go.
pytestmark = pytest.mark.legacy


def test_ntcp_with_synthetic_data(synthetic_data_dir, ntcp_template, temp_output_dir):
    """Test complete NTCP analysis"""
    
    # Use NTCP clinical file from synthetic data if available, otherwise use template
    if 'ntcp_clinical_file' in synthetic_data_dir and Path(synthetic_data_dir['ntcp_clinical_file']).exists():
        clinical_file = synthetic_data_dir['ntcp_clinical_file']
    else:
        clinical_file = ntcp_template
    
    cmd = [
        sys.executable,
        "legacy/code3_ntcp_analysis_ml.py",
        "--dvh_dir", str(synthetic_data_dir.get('dvh_dir', synthetic_data_dir.get('output_dir'))),
        "--patient_data", str(clinical_file),
        "--output_dir", str(temp_output_dir),
        "--ml_models"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=Path.cwd())
    
    assert result.returncode == 0, f"NTCP failed: {result.stderr}"
    
    # Check outputs (may have different names)
    pred_file = temp_output_dir / "ntcp_predictions.xlsx"
    if not pred_file.exists():
        pred_file = temp_output_dir / "enhanced_ntcp_results.xlsx"
    
    assert pred_file.exists(), "NTCP predictions missing"
    
    # Validate predictions
    pred_df = pd.read_excel(pred_file)
    assert 'PatientID' in pred_df.columns or 'Patient_ID' in pred_df.columns
    assert 'Organ' in pred_df.columns
    
    # Check NTCP values
    ntcp_cols = [col for col in pred_df.columns if col.startswith('NTCP_') or col.startswith('LKB_') or col.startswith('RS_')]
    for col in ntcp_cols:
        if pred_df[col].dtype in [np.float64, np.float32, float]:
            assert pred_df[col].min() >= 0, f"{col} has values < 0"
            assert pred_df[col].max() <= 1, f"{col} has values > 1"


def test_ntcp_validation(synthetic_data_dir, temp_output_dir):
    """The clinical-data validation must reject a file with missing required columns.

    Defect #57. This test used to pass `--dvh_dir test_data/DVH_files`, a path that does not exist
    in the repository, so the script printed "DVH directory not found" and exited 1 before it ever
    opened the clinical file. The assertion accepted `result.returncode != 0` as one of its
    disjuncts, so a non-zero exit from *any* cause satisfied it: the test passed without the
    validation code running at all, and would have kept passing if that code were deleted. On the
    CI core job, where seaborn is absent, it passed a third way -- on the import error.

    It now takes the same `synthetic_data_dir` fixture its siblings use, so the script gets a real
    DVH directory and reaches the clinical file, and the assertion requires evidence that
    *validation* rejected the file rather than merely that the process failed.
    """
    # A clinical file with none of the required columns.
    invalid_clinical = temp_output_dir / "invalid_clinical.xlsx"
    df = pd.DataFrame({
        'Patient': ['P001', 'P002'],
        'Value': [1, 0]
    })
    df.to_excel(invalid_clinical, index=False)

    dvh_dir = synthetic_data_dir.get('dvh_dir', synthetic_data_dir.get('output_dir'))
    cmd = [
        sys.executable,
        "legacy/code3_ntcp_analysis_ml.py",
        "--dvh_dir", str(dvh_dir),
        "--patient_data", str(invalid_clinical),
        "--output_dir", str(temp_output_dir)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=Path.cwd())
    combined = (result.stdout + result.stderr).lower()

    # It must not have died before reaching the clinical file.
    assert not ("dvh directory" in combined and "not found" in combined), (
        "the script exited on a missing DVH directory, so clinical validation never ran -- this is "
        "the #57 failure mode returning.\nstdout tail:\n" + result.stdout[-1500:]
    )

    # And it must say the clinical data was rejected, not merely fail.
    validation_signals = (
        "missing required column",
        "validation failed",
        "required column",
        "patientid",
    )
    assert any(sig in combined for sig in validation_signals), (
        "no validation message found; a non-zero exit code alone is not evidence that the "
        "validation code ran.\nreturncode=" + str(result.returncode)
        + "\nstdout tail:\n" + result.stdout[-1500:]
        + "\nstderr tail:\n" + result.stderr[-1500:]
    )

