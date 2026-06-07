"""Test NTCP analysis workflow"""
import pytest
import subprocess
import sys
from pathlib import Path
import pandas as pd
import numpy as np


def test_ntcp_with_synthetic_data(synthetic_data_dir, ntcp_template, temp_output_dir):
    """Test complete NTCP analysis"""
    
    # Use NTCP clinical file from synthetic data if available, otherwise use template
    if 'ntcp_clinical_file' in synthetic_data_dir and Path(synthetic_data_dir['ntcp_clinical_file']).exists():
        clinical_file = synthetic_data_dir['ntcp_clinical_file']
    else:
        clinical_file = ntcp_template
    
    cmd = [
        sys.executable,
        "code3_ntcp_analysis_ml.py",
        "--dvh_dir", str(synthetic_data_dir.get('dvh_dir', synthetic_data_dir.get('output_dir'))),
        "--patient_data", str(clinical_file),
        "--output_dir", str(temp_output_dir),
        "--ml_models"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
    
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


def test_ntcp_validation(ntcp_template, temp_output_dir):
    """Test NTCP clinical data validation"""
    
    # Test with invalid data (missing required columns)
    invalid_clinical = temp_output_dir / "invalid_clinical.xlsx"
    df = pd.DataFrame({
        'Patient': ['P001', 'P002'],
        'Value': [1, 0]
    })
    df.to_excel(invalid_clinical, index=False)
    
    cmd = [
        sys.executable,
        "code3_ntcp_analysis_ml.py",
        "--dvh_dir", "test_data/DVH_files",
        "--patient_data", str(invalid_clinical),
        "--output_dir", str(temp_output_dir)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
    
    # Should fail with validation error
    assert result.returncode != 0 or "validation failed" in result.stdout.lower() or \
           "Missing required columns" in result.stdout or \
           "PatientID" in result.stderr, "Validation should have failed"

