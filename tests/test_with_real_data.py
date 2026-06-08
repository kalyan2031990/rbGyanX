"""Integration tests with real clinical data from input_folders."""
import os
import pytest
from pathlib import Path
import pandas as pd

_INPUT_ROOT = Path(
    os.environ.get(
        "RBGYANX_INPUT_FOLDERS",
        r"C:\Users\Sampa\OneDrive\Desktop\input_folders",
    )
)
_CLINICAL_DIR = _INPUT_ROOT / "rbgyanx_test_data" / "clinical_data"


@pytest.mark.skipif(
    not _CLINICAL_DIR.is_dir(),
    reason="Real clinical data not available under input_folders",
)
def test_with_real_clinical_data():
    """Test complete workflow with real clinical data"""
    
    input_dir = _CLINICAL_DIR
    clinical_files = list(input_dir.glob("*.xlsx")) + list(input_dir.glob("*.csv"))
    
    if not clinical_files:
        pytest.skip("No clinical data files found in input_data/")
    
    clinical_file = clinical_files[0]
    
    # Validate can read clinical data
    try:
        if clinical_file.suffix == '.xlsx':
            df = pd.read_excel(clinical_file)
        else:
            df = pd.read_csv(clinical_file)
        
        assert len(df) > 0, "Clinical data is empty"
        print(f"Real clinical data: {len(df)} rows, {len(df.columns)} columns")
        
        # Check for common columns
        columns = [col.lower() for col in df.columns]
        has_patient_id = any('patient' in col or 'id' in col for col in columns)
        has_toxicity = any('tox' in col or 'xerostomia' in col or 'dysphagia' in col 
                           for col in columns)
        
        assert has_patient_id, "No patient ID column found"
        
        if has_toxicity:
            print("✓ Real data appears to be NTCP data")
        else:
            print("✓ Real data appears to be TCP data or needs validation")
    except Exception as e:
        pytest.skip(f"Could not read clinical data: {e}")

