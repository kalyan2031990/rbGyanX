"""Test TCP-NTCP integration"""
import pytest
import subprocess
import sys
from pathlib import Path
import pandas as pd


def test_full_integration_workflow(synthetic_data_dir, tcp_template, ntcp_template, temp_output_dir):
    """Test complete TCP+NTCP+Integration workflow"""
    
    tcp_dir = temp_output_dir / "tcp_analysis"
    ntcp_dir = temp_output_dir / "ntcp_analysis"
    int_dir = temp_output_dir / "integration"
    
    # 1. Run TCP
    tcp_cmd = [
        sys.executable,
        "code6_tcp_analysis.py",
        "--tumor_dvh_dir", str(synthetic_data_dir['tumor_dvh_dir']),
        "--clinical_xlsx", str(tcp_template),
        "--outdir", str(tcp_dir),
        "--enable_ml"
    ]
    result = subprocess.run(tcp_cmd, capture_output=True, text=True, cwd=Path.cwd())
    assert result.returncode == 0, f"TCP failed: {result.stderr}"
    
    # 2. Run NTCP
    if 'ntcp_clinical_file' in synthetic_data_dir and Path(synthetic_data_dir['ntcp_clinical_file']).exists():
        clinical_file = synthetic_data_dir['ntcp_clinical_file']
    else:
        clinical_file = ntcp_template
    
    ntcp_cmd = [
        sys.executable,
        "code3_ntcp_analysis_ml.py",
        "--dvh_dir", str(synthetic_data_dir.get('dvh_dir', synthetic_data_dir.get('output_dir'))),
        "--patient_data", str(clinical_file),
        "--output_dir", str(ntcp_dir),
        "--ml_models"
    ]
    result = subprocess.run(ntcp_cmd, capture_output=True, text=True, cwd=Path.cwd())
    assert result.returncode == 0, f"NTCP failed: {result.stderr}"
    
    # 3. Run Integration
    int_cmd = [
        sys.executable,
        "code7_tcp_ntcp_integration.py",
        "--tcp_dir", str(tcp_dir),
        "--ntcp_dir", str(ntcp_dir),
        "--output_dir", str(int_dir)
    ]
    result = subprocess.run(int_cmd, capture_output=True, text=True, cwd=Path.cwd())
    assert result.returncode == 0, f"Integration failed: {result.stderr}"
    
    # Verify integration outputs
    assert (int_dir / "therapeutic_ratios.xlsx").exists()
    
    # Check plots
    plots_dir = int_dir / "plots"
    assert plots_dir.exists()
    
    # Check for expected plot files (may have different names)
    plot_files = list(plots_dir.glob("*.png"))
    assert len(plot_files) > 0, "No integration plots generated"
    
    # Validate therapeutic ratios
    ratios_df = pd.read_excel(int_dir / "therapeutic_ratios.xlsx")
    assert 'PatientID' in ratios_df.columns or 'Patient_ID' in ratios_df.columns
    assert 'UTCP' in ratios_df.columns
    assert 'P_Plus' in ratios_df.columns or 'P_plus' in ratios_df.columns or 'P+' in ratios_df.columns
    
    # Check values in valid range
    if 'UTCP' in ratios_df.columns:
        utcp_values = ratios_df['UTCP'].dropna()
        if len(utcp_values) > 0:
            assert utcp_values.min() >= 0, "UTCP has values < 0"
            assert utcp_values.max() <= 1, "UTCP has values > 1"

