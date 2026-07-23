"""Test clinical template generation"""
import pytest
import pandas as pd
from pathlib import Path


def test_tcp_template_creation(tcp_template):
    """Test TCP template creates valid Excel file"""
    assert Path(tcp_template).exists()
    
    # Load and check sheets
    excel_file = pd.ExcelFile(tcp_template)
    assert 'ClinicalData' in excel_file.sheet_names
    assert 'ColumnDescriptions' in excel_file.sheet_names
    assert 'Instructions' in excel_file.sheet_names
    
    # Check data sheet
    df = pd.read_excel(tcp_template, sheet_name='ClinicalData')
    assert 'PatientID' in df.columns
    assert 'TumorControl' in df.columns
    assert len(df) == 30  # Default sample size
    
    # Check data types
    assert df['TumorControl'].isin([0, 1]).all()


def test_ntcp_template_creation(ntcp_template):
    """Test NTCP template creates valid Excel file"""
    assert Path(ntcp_template).exists()
    
    df = pd.read_excel(ntcp_template, sheet_name='ClinicalData')
    assert 'PatientID' in df.columns
    assert 'Organ' in df.columns
    assert 'Toxicity' in df.columns


def test_template_sample_data_realistic(tcp_template):
    """Test template sample data is realistic"""
    df = pd.read_excel(tcp_template, sheet_name='ClinicalData')
    
    # Check age range
    if 'Age' in df.columns:
        assert df['Age'].min() >= 30
        assert df['Age'].max() <= 90
    
    # Check stage distribution
    if 'Stage' in df.columns:
        stages = df['Stage'].unique()
        assert all(s in ['I', 'II', 'III', 'IVA', 'IVB'] for s in stages)
    
    # Check tumor control rate reasonable
    tc_rate = df['TumorControl'].mean()
    assert 0.5 < tc_rate < 0.9  # Should be 50-90%

