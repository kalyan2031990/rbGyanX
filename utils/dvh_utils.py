"""
DVH manipulation utilities
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple


def calculate_dose_metrics(dvh_df: pd.DataFrame, 
                           dose_column: str = 'Dose_Gy', 
                           volume_column: str = 'Relative_Volume') -> Dict[str, float]:
    """
    Calculate standard dose metrics from DVH
    
    Parameters
    ----------
    dvh_df : pd.DataFrame
        DVH data with dose and volume columns
    dose_column : str
        Name of dose column
    volume_column : str
        Name of volume column (cumulative or differential)
    
    Returns
    -------
    dict
        Dictionary with dose metrics (Dmean, Dmax, Dmin, D95, D98, etc.)
    """
    if dvh_df.empty:
        return {}
    
    # Ensure cumulative DVH
    if volume_column in dvh_df.columns:
        cumulative = convert_to_cumulative(dvh_df, dose_column, volume_column)
    else:
        cumulative = dvh_df.copy()
    
    metrics = {
        'Dmean': calculate_mean_dose(cumulative, dose_column),
        'Dmax': cumulative[dose_column].max() if dose_column in cumulative.columns else 0.0,
        'Dmin': cumulative[dose_column].min() if dose_column in cumulative.columns else 0.0,
        'D95': get_dose_at_volume(cumulative, dose_column, 95),
        'D98': get_dose_at_volume(cumulative, dose_column, 98),
        'D50': get_dose_at_volume(cumulative, dose_column, 50),
        'D2': get_dose_at_volume(cumulative, dose_column, 2),
        'V20Gy': get_volume_at_dose(cumulative, dose_column, volume_column, 20),
        'V30Gy': get_volume_at_dose(cumulative, dose_column, volume_column, 30),
        'V40Gy': get_volume_at_dose(cumulative, dose_column, volume_column, 40)
    }
    
    return metrics


def convert_to_cumulative(dvh_df: pd.DataFrame, 
                          dose_column: str = 'Dose_Gy',
                          volume_column: str = 'Relative_Volume') -> pd.DataFrame:
    """
    Convert differential DVH to cumulative DVH
    
    Parameters
    ----------
    dvh_df : pd.DataFrame
        Differential DVH data
    dose_column : str
        Name of dose column
    volume_column : str
        Name of volume column
    
    Returns
    -------
    pd.DataFrame
        Cumulative DVH
    """
    if dvh_df.empty:
        return dvh_df
    
    result = dvh_df.copy()
    
    # Sort by dose descending
    result = result.sort_values(dose_column, ascending=False)
    
    # Calculate cumulative volume
    if volume_column in result.columns:
        result[volume_column] = result[volume_column].cumsum()
    
    return result


def convert_cumulative_to_differential(cumulative_dvh: pd.DataFrame,
                                       dose_column: str = 'Dose_Gy',
                                       volume_column: str = 'Relative_Volume') -> pd.DataFrame:
    """
    Convert cumulative DVH to differential DVH
    
    Parameters
    ----------
    cumulative_dvh : pd.DataFrame
        Cumulative DVH data
    dose_column : str
        Name of dose column
    volume_column : str
        Name of volume column
    
    Returns
    -------
    pd.DataFrame
        Differential DVH
    """
    if cumulative_dvh.empty:
        return cumulative_dvh
    
    result = cumulative_dvh.copy()
    
    # Sort by dose descending
    result = result.sort_values(dose_column, ascending=False)
    
    # Calculate differential volume
    if volume_column in result.columns:
        result[volume_column] = result[volume_column].diff().fillna(result[volume_column].iloc[0])
        result[volume_column] = result[volume_column].abs()
    
    return result


def convert_differential_to_cumulative(differential_dvh: pd.DataFrame,
                                      dose_column: str = 'Dose_Gy',
                                      volume_column: str = 'Relative_Volume') -> pd.DataFrame:
    """
    Convert differential DVH to cumulative DVH (alias for convert_to_cumulative)
    
    Parameters
    ----------
    differential_dvh : pd.DataFrame
        Differential DVH data
    dose_column : str
        Name of dose column
    volume_column : str
        Name of volume column
    
    Returns
    -------
    pd.DataFrame
        Cumulative DVH
    """
    return convert_to_cumulative(differential_dvh, dose_column, volume_column)


def calculate_mean_dose(dvh_df: pd.DataFrame, dose_column: str = 'Dose_Gy') -> float:
    """Calculate mean dose from DVH"""
    if dvh_df.empty or dose_column not in dvh_df.columns:
        return 0.0
    
    return float(dvh_df[dose_column].mean())


def get_dose_at_volume(dvh_df: pd.DataFrame, 
                       dose_column: str = 'Dose_Gy',
                       volume_percent: float = 95) -> float:
    """
    Get dose at specified volume percentage
    
    Parameters
    ----------
    dvh_df : pd.DataFrame
        Cumulative DVH data
    dose_column : str
        Name of dose column
    volume_percent : float
        Volume percentage (0-100)
    
    Returns
    -------
    float
        Dose at specified volume
    """
    if dvh_df.empty or dose_column not in dvh_df.columns:
        return 0.0
    
    # Find volume column
    volume_col = None
    for col in dvh_df.columns:
        if 'volume' in col.lower() or 'vol' in col.lower():
            volume_col = col
            break
    
    if volume_col is None:
        return 0.0
    
    # Interpolate to find dose at volume_percent
    sorted_df = dvh_df.sort_values(volume_col, ascending=False)
    
    if volume_percent > sorted_df[volume_col].max():
        return float(sorted_df[dose_column].iloc[-1])
    if volume_percent < sorted_df[volume_col].min():
        return float(sorted_df[dose_column].iloc[0])
    
    # Interpolate
    dose_at_vol = np.interp(volume_percent, sorted_df[volume_col], sorted_df[dose_column])
    
    return float(dose_at_vol)


def get_volume_at_dose(dvh_df: pd.DataFrame,
                       dose_column: str = 'Dose_Gy',
                       volume_column: str = 'Relative_Volume',
                       dose_gy: float = 20.0) -> float:
    """
    Get volume at specified dose
    
    Parameters
    ----------
    dvh_df : pd.DataFrame
        Cumulative DVH data
    dose_column : str
        Name of dose column
    volume_column : str
        Name of volume column
    dose_gy : float
        Dose in Gray
    
    Returns
    -------
    float
        Volume at specified dose
    """
    if dvh_df.empty or dose_column not in dvh_df.columns:
        return 0.0
    
    if volume_column not in dvh_df.columns:
        return 0.0
    
    # Sort by dose
    sorted_df = dvh_df.sort_values(dose_column, ascending=False)
    
    # Interpolate to find volume at dose
    if dose_gy > sorted_df[dose_column].max():
        return 0.0
    if dose_gy < sorted_df[dose_column].min():
        return float(sorted_df[volume_column].iloc[-1])
    
    volume_at_dose = np.interp(dose_gy, sorted_df[dose_column], sorted_df[volume_column])
    
    return float(volume_at_dose)

