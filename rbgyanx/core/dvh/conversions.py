"""
DVH Conversion Functions

This module provides pure computational functions for converting between
cumulative and differential DVH formats.

Layer 1 (Core): Pure computational functions.
"""

import numpy as np
import pandas as pd
from typing import Union


def convert_to_cumulative(ddvh: pd.DataFrame) -> pd.DataFrame:
    """
    Convert differential DVH to cumulative DVH.
    
    This function handles both absolute differential DVH (dV in cm³) and
    normalized differential DVH (dV/dD in %/Gy or cm³/Gy). The conversion
    automatically detects the format based on the magnitude of volume values.
    
    Mathematical Formulation:
    For absolute dV:
        V_cum(D) = Σ[dV(d)] for d >= D
    
    For normalized dV/dD:
        dV = (dV/dD) * dD
        V_cum(D) = Σ[dV(d)] for d >= D
    
    Parameters
    ----------
    ddvh : pd.DataFrame
        Differential DVH with columns:
        - 'Dose[Gy]': Dose values (Gy) for each bin
        - 'Volume[cm3]': Volume values (cm³) or normalized volume (dV/dD)
    
    Returns
    -------
    pd.DataFrame
        Cumulative DVH with columns:
        - 'Dose[Gy]': Dose values (Gy) - same as input
        - 'Volume[cm3]': Cumulative volume (cm³) receiving at least that dose
    
    Notes
    -----
    - Automatically detects whether input is absolute dV or normalized dV/dD
    - Detection heuristic: if max volume < 10, assumes normalized dV/dD
    - Cumulative volume is calculated by integrating from high dose to low dose
    - The output cumulative DVH is monotonically non-increasing
    
    References
    ----------
    - ICRU Report 50: Prescribing, Recording, and Reporting Photon Beam Therapy
    - ICRU Report 83: Prescribing, Recording, and Reporting Intensity-Modulated
      Photon-Beam Therapy (IMRT)
    """
    cdvh = ddvh.copy()
    
    # Extract dose and volume arrays
    doses = ddvh['Dose[Gy]'].values
    diff_volumes = ddvh['Volume[cm3]'].values  # This is dV or dV/dD
    
    # Check if it's dV/dD (normalized) or just dV
    # If maximum value < 10, it's likely dV/dD in %/Gy or cm³/Gy
    if diff_volumes.max() < 10:
        # It's dV/dD in %/Gy or cm³/Gy - need to multiply by bin width
        dose_bins = np.diff(doses)
        dose_bins = np.append(dose_bins, dose_bins[-1] if len(dose_bins) > 0 else 0)  # Extend to match length
        absolute_dv = diff_volumes * dose_bins  # dV = (dV/dD) * dD
    else:
        # It's already dV in cm³
        absolute_dv = diff_volumes
    
    # Integrate from high dose to low dose (reverse cumsum)
    # Cumulative volume at dose D is the sum of all volumes at doses >= D
    cumulative_volume = np.cumsum(absolute_dv[::-1])[::-1]
    
    cdvh['Volume[cm3]'] = cumulative_volume
    return cdvh


def convert_to_differential(cdvh: pd.DataFrame) -> pd.DataFrame:
    """
    Convert cumulative DVH to differential DVH.
    
    This function calculates the differential volume in each dose bin by
    taking the negative difference of cumulative volumes.
    
    Mathematical Formulation:
        dV(D) = -d[V_cum(D)]/dD
    
    For discrete bins:
        dV_i = -(V_cum,i - V_cum,i-1) = V_cum,i-1 - V_cum,i
    
    Parameters
    ----------
    cdvh : pd.DataFrame
        Cumulative DVH with columns:
        - 'Dose[Gy]': Dose values (Gy) for each bin
        - 'Volume[cm3]': Cumulative volume (cm³) receiving at least that dose
    
    Returns
    -------
    pd.DataFrame
        Differential DVH with columns:
        - 'Dose[Gy]': Dose values (Gy) - same as input
        - 'Volume[cm3]': Differential volume (cm³) in each dose bin
    
    Notes
    -----
    - Input cumulative DVH should be monotonically non-increasing
    - Differential volume is calculated as the negative difference between
      consecutive cumulative volumes
    - The last bin gets the remaining cumulative volume
    - Output differential volumes are always non-negative
    
    References
    ----------
    - ICRU Report 50: Prescribing, Recording, and Reporting Photon Beam Therapy
    - ICRU Report 83: Prescribing, Recording, and Reporting Intensity-Modulated
      Photon-Beam Therapy (IMRT)
    """
    ddvh = cdvh.copy()
    volumes = cdvh['Volume[cm3]'].values
    
    # Calculate differences (negative diff for decreasing cumulative)
    # prepend volumes[0] to handle the first bin correctly
    diff_volumes = -np.diff(volumes, prepend=volumes[0])
    
    # Last bin gets the remaining volume (should be the minimum cumulative volume)
    diff_volumes[-1] = volumes[-1]
    
    ddvh['Volume[cm3]'] = diff_volumes
    return ddvh

