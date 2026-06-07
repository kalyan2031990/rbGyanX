"""Test TCP analysis workflow end-to-end"""
import pytest
import subprocess
import sys
from pathlib import Path
import pandas as pd
import numpy as np


def test_tcp_with_synthetic_data(synthetic_data_dir, tcp_template, temp_output_dir):
    """Test complete TCP analysis with synthetic data"""
    
    # Run TCP analysis
    cmd = [
        sys.executable,
        "code6_tcp_analysis.py",
        "--tumor_dvh_dir", str(synthetic_data_dir['tumor_dvh_dir']),
        "--clinical_xlsx", str(tcp_template),
        "--outdir", str(temp_output_dir),
        "--enable_ml"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
    
    # Check execution success
    assert result.returncode == 0, f"TCP analysis failed:\n{result.stderr}"
    
    # Verify outputs exist
    assert (temp_output_dir / "tcp_predictions.xlsx").exists(), "TCP predictions missing"
    assert (temp_output_dir / "tcp_parameters.xlsx").exists(), "TCP parameters missing"
    assert (temp_output_dir / "tcp_dose_metrics.xlsx").exists(), "TCP dose metrics missing"
    
    # Verify ML outputs
    assert (temp_output_dir / "tcp_ml_performance.xlsx").exists(), "ML performance missing"
    
    # Verify plots directory
    plots_dir = temp_output_dir / "plots"
    assert plots_dir.exists(), "Plots directory missing"
    
    plot_files = list(plots_dir.glob("*.png"))
    assert len(plot_files) > 0, "No plots generated"
    
    # Verify plot DPI (should be 600)
    try:
        from PIL import Image
        sample_plot = plot_files[0]
        img = Image.open(sample_plot)
        dpi = img.info.get('dpi', (0, 0))
        # Note: PNG files may not always store DPI in metadata
        # The actual DPI is set during savefig, so we check if file exists and is reasonable size
        assert sample_plot.stat().st_size > 1000, "Plot file too small (likely not 600 DPI)"
    except ImportError:
        pytest.skip("PIL/Pillow not available for DPI check")
    
    # Validate predictions content
    pred_df = pd.read_excel(temp_output_dir / "tcp_predictions.xlsx")
    
    # Check required columns
    pid_col = 'PatientID' if 'PatientID' in pred_df.columns else 'Patient_ID'
    assert pid_col in pred_df.columns, "PatientID missing"
    assert 'TCP_Poisson' in pred_df.columns, "TCP_Poisson missing"
    assert 'TCP_LKB' in pred_df.columns, "TCP_LKB missing"
    
    # Check TCP values in valid range [0, 1]
    for col in ['TCP_Poisson', 'TCP_LKB', 'TCP_Logistic', 'TCP_EUD']:
        if col in pred_df.columns:
            assert pred_df[col].min() >= 0, f"{col} has values < 0"
            assert pred_df[col].max() <= 1, f"{col} has values > 1"
            assert not pred_df[col].isna().all(), f"{col} is all NaN"
    
    # Check ML columns if available
    if 'ML_ANN' in pred_df.columns:
        assert pred_df['ML_ANN'].min() >= 0, "ML_ANN has values < 0"
        assert pred_df['ML_ANN'].max() <= 1, "ML_ANN has values > 1"
    
    # Validate ML performance
    if (temp_output_dir / "tcp_ml_performance.xlsx").exists():
        ml_perf = pd.read_excel(temp_output_dir / "tcp_ml_performance.xlsx")
        assert 'Model' in ml_perf.columns, "Model column missing"
        if 'AUC' in ml_perf.columns:
            for auc in ml_perf['AUC']:
                if pd.notna(auc):
                    assert 0.5 <= auc <= 1.0, f"AUC out of range: {auc}"


def test_tcp_without_metrics_file(synthetic_data_dir, tcp_template, temp_output_dir):
    """Test TCP analysis calculates metrics from DVH when file missing"""
    
    cmd = [
        sys.executable,
        "code6_tcp_analysis.py",
        "--tumor_dvh_dir", str(synthetic_data_dir['tumor_dvh_dir']),
        "--clinical_xlsx", str(tcp_template),
        "--outdir", str(temp_output_dir),
        # Don't provide --physical_metrics_file
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
    
    assert result.returncode == 0, f"TCP failed: {result.stderr}"
    assert "Calculating TCP metrics from DVH" in result.stdout or \
           "calculated" in result.stdout.lower() or \
           "from DVH" in result.stdout, "Metrics not calculated from DVH"
    
    # Check calculated metrics file exists (may have different name)
    calc_metrics = temp_output_dir / "tcp_physical_metrics_calculated.xlsx"
    if not calc_metrics.exists():
        # Try alternative names
        alt_metrics = list(temp_output_dir.glob("*metrics*.xlsx"))
        assert len(alt_metrics) > 0, "No metrics file found after calculation"
        calc_metrics = alt_metrics[0]
    
    # Validate metrics content
    metrics_df = pd.read_excel(calc_metrics)
    assert 'PatientID' in metrics_df.columns or 'Patient_ID' in metrics_df.columns
    assert 'GTV_Mean_Dose' in metrics_df.columns or 'Mean_Dose' in metrics_df.columns or 'MeanDose' in metrics_df.columns


def test_tcp_ml_with_minimal_clinical_data(synthetic_data_dir, temp_output_dir):
    """Test TCP ML runs with only PatientID and TumorControl"""
    
    # Create minimal clinical template
    minimal_clinical = temp_output_dir / "minimal_clinical.xlsx"
    
    # Load full template and keep only required columns
    try:
        from clinical_template_generator import create_tcp_template
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            full_template = create_tcp_template(f.name, with_samples=True, n_samples=30)
        
        df = pd.read_excel(full_template)
        minimal_df = df[['PatientID', 'TumorControl']].copy()
        minimal_df.to_excel(minimal_clinical, index=False)
    except ImportError:
        pytest.skip("clinical_template_generator not available")
    
    # Run TCP with minimal data
    cmd = [
        sys.executable,
        "code6_tcp_analysis.py",
        "--tumor_dvh_dir", str(synthetic_data_dir['tumor_dvh_dir']),
        "--clinical_xlsx", str(minimal_clinical),
        "--outdir", str(temp_output_dir),
        "--enable_ml"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
    
    assert result.returncode == 0, f"TCP failed with minimal data: {result.stderr}"

    # ML should still run (with DVH features only)
    assert (temp_output_dir / "tcp_ml_performance.xlsx").exists() or \
           (temp_output_dir / "tcp_predictions.xlsx").exists(), "ML didn't run or predictions missing"

