"""
Data validation utilities
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict


def validate_dvh_file(dvh_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Validate DVH file format
    
    Parameters
    ----------
    dvh_path : Path
        Path to DVH file
    
    Returns
    -------
    tuple
        (is_valid, error_message)
    """
    if not dvh_path.exists():
        return False, f"File not found: {dvh_path}"
    
    try:
        # Try to read as CSV
        df = pd.read_csv(dvh_path, nrows=5)
        
        # Check for required columns (dose and volume)
        has_dose = any('dose' in col.lower() for col in df.columns)
        has_volume = any('volume' in col.lower() or 'vol' in col.lower() for col in df.columns)
        
        if not has_dose:
            return False, "No dose column found"
        if not has_volume:
            return False, "No volume column found"
        
        return True, None
        
    except Exception as e:
        return False, f"Error reading file: {str(e)}"


def validate_clinical_data(clinical_df: pd.DataFrame, 
                          required_columns: List[str]) -> Tuple[bool, Optional[str], List[str]]:
    """
    Validate clinical data DataFrame
    
    Parameters
    ----------
    clinical_df : pd.DataFrame
        Clinical data
    required_columns : List[str]
        List of required column names
    
    Returns
    -------
    tuple
        (is_valid, error_message, missing_columns)
    """
    if clinical_df.empty:
        return False, "Clinical data is empty", required_columns
    
    missing = [col for col in required_columns if col not in clinical_df.columns]
    
    if missing:
        return False, f"Missing required columns: {missing}", missing
    
    # Check for PatientID column
    patient_id_cols = [col for col in clinical_df.columns 
                      if col.lower() in ['patientid', 'patient_id', 'id']]
    
    if not patient_id_cols:
        return False, "No PatientID column found", ['PatientID']
    
    return True, None, []


def validate_patient_id_format(patient_ids: pd.Series) -> Tuple[bool, Optional[str]]:
    """
    Validate patient ID format
    
    Parameters
    ----------
    patient_ids : pd.Series
        Patient ID series
    
    Returns
    -------
    tuple
        (is_valid, error_message)
    """
    if patient_ids.empty:
        return False, "Patient IDs are empty"
    
    # Check for duplicates
    duplicates = patient_ids.duplicated()
    if duplicates.any():
        dup_ids = patient_ids[duplicates].unique()
        return False, f"Duplicate patient IDs found: {list(dup_ids)[:5]}"
    
    # Check for missing values
    if patient_ids.isna().any():
        return False, "Missing patient IDs found"
    
    return True, None


def validate_dose_range(dose_values: np.ndarray, 
                       min_dose: float = 0.0, 
                       max_dose: float = 100.0) -> Tuple[bool, Optional[str]]:
    """
    Validate dose values are in reasonable range
    
    Parameters
    ----------
    dose_values : np.ndarray
        Dose values
    min_dose : float
        Minimum acceptable dose
    max_dose : float
        Maximum acceptable dose
    
    Returns
    -------
    tuple
        (is_valid, error_message)
    """
    if len(dose_values) == 0:
        return False, "No dose values provided"
    
    if np.any(dose_values < min_dose):
        return False, f"Some dose values below minimum ({min_dose} Gy)"
    
    if np.any(dose_values > max_dose):
        return False, f"Some dose values above maximum ({max_dose} Gy)"
    
    return True, None


def validate_outcome_column(outcome_values: pd.Series, 
                            binary: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate outcome column (e.g., toxicity, tumor control)
    
    Parameters
    ----------
    outcome_values : pd.Series
        Outcome values
    binary : bool
        Whether outcome should be binary (0/1)
    
    Returns
    -------
    tuple
        (is_valid, error_message)
    """
    if outcome_values.empty:
        return False, "Outcome values are empty"
    
    if outcome_values.isna().any():
        return False, "Missing outcome values found"
    
    if binary:
        unique_values = outcome_values.unique()
        valid_values = {0, 1, 0.0, 1.0, True, False}
        
        if not all(v in valid_values for v in unique_values):
            return False, f"Outcome values must be binary (0/1), found: {unique_values}"
    
    return True, None

