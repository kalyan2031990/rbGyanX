"""
Module: rbgyanx/core/tcp/eud.py
Layer: 1 (Core - Deterministic Analytical)
Purpose: TCP calculation using EUD-based model

Mathematical Formulation:
-------------------------
EUD-based TCP Model (Niemierko, 1997)

Uses Equivalent Uniform Dose (EUD) concept:

EUD = (Σ(vᵢ · Dᵢ^a) / Σvᵢ)^(1/a)

TCP = 1 / (1 + (D50/EUD_eqd2)^(4·γ₅₀))

where:
    vᵢ = volume of dose bin i
    Dᵢ = dose in bin i (converted to EQD2)
    a = volume effect parameter (typically -10 to -20 for tumors)
    D50 = dose for 50% TCP (Gy)
    γ₅₀ = slope parameter

References:
-----------
Niemierko A (1997). Reporting and analyzing dose distributions: a concept
of equivalent uniform dose. Med Phys. 24(1):103-110.

Niemierko A (1999). A generalized concept of equivalent uniform dose.
Med Phys. 26(6):1100.
"""

from typing import Optional
import numpy as np
import pandas as pd
from rbgyanx.core.dvh_columns import normalize_dvh_columns
from rbgyanx.core.tcp._eqd2 import convert_to_eqd2


def calculate_tcp_eud(
    dvh: pd.DataFrame,
    D50: float,
    gamma50: float,
    a: float = -10.0,
    alpha_beta: float = 10.0,
    dose_per_fraction: float = 2.0
) -> float:
    """
    Calculate TCP using EUD-based model.
    
    This function implements the Equivalent Uniform Dose (EUD) based TCP model,
    matching the original TCPCalculator.tcp_eud implementation.
    
    Parameters
    ----------
    dvh : pd.DataFrame
        Differential DVH with columns 'dose_gy' and 'volume_cm3'
        Dose values should be in Gy, volume in cm³
    D50 : float
        Dose for 50% TCP (Gy)
    gamma50 : float
        Slope parameter (dimensionless, typically 1.5-3.0)
    a : float, optional
        Volume effect parameter (typically -10 to -20 for tumors, default: -10.0)
    alpha_beta : float, optional
        α/β ratio for biological normalization (Gy, default: 10.0)
    dose_per_fraction : float, optional
        Dose per fraction for biological normalization (Gy, default: 2.0)
    
    Returns
    -------
    float
        TCP value (0-1)
    
    Notes
    -----
    - Assumes photon therapy
    - Uses EQD2 conversion for dose normalization
    - Parameter 'a' is negative for tumors (typical range: -10 to -20)
    - Original implementation from utils.tcp_models.TCPCalculator.tcp_eud
    """
    if dvh is None or len(dvh) == 0:
        return 0.0
    if D50 <= 0:
        raise ValueError("D50 must be positive")
    if gamma50 <= 0:
        raise ValueError("gamma50 must be positive")

    try:
        dvh = normalize_dvh_columns(dvh)
        doses = dvh["dose_gy"].values
        vol_col = "volume_cm3" if "volume_cm3" in dvh.columns else "volume_frac"
        volumes = dvh[vol_col].values
        total_volume = np.sum(volumes)
        
        if total_volume <= 0:
            return 0.0
        
        # Calculate relative volumes
        rel_volumes = volumes / total_volume
        
        # Convert doses to EQD2
        doses_eqd2 = np.array([convert_to_eqd2(d, alpha_beta, dose_per_fraction)
                              for d in doses])
        
        # Calculate EUD
        # Filter out zero doses to avoid numerical issues
        valid_mask = doses_eqd2 > 1e-6
        if not np.any(valid_mask):
            return 0.0
        
        valid_doses = doses_eqd2[valid_mask]
        valid_volumes = rel_volumes[valid_mask]
        valid_volumes = valid_volumes / np.sum(valid_volumes)  # Renormalize
        
        if a == 0:
            # Limit case: EUD = geometric mean
            eud = np.exp(np.sum(valid_volumes * np.log(valid_doses)))
        else:
            # General case: EUD = (sum(vi * Di^a))^(1/a)
            # For negative a, we need to be careful with the calculation
            powered_doses = np.power(valid_doses, a)
            weighted_sum = np.sum(valid_volumes * powered_doses)
            if weighted_sum <= 0:
                return 0.0
            eud = np.power(weighted_sum, 1.0 / a)
            if np.isnan(eud) or np.isinf(eud) or eud <= 0:
                return 0.0
        
        # Calculate TCP using EUD
        # TCP = 1 / (1 + (D50/EUD)^(4*gamma50))
        ratio = D50 / eud
        exponent = 4.0 * gamma50
        tcp = 1.0 / (1.0 + np.power(ratio, exponent))
        
        # Clip to valid range
        tcp = np.clip(tcp, 1e-15, 1.0 - 1e-15)
        return float(tcp)
        
    except (OverflowError, ZeroDivisionError, ValueError):
        return 0.0


__all__ = ['calculate_tcp_eud']
