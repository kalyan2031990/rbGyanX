"""
Module: rbgyanx/core/tcp/_eqd2.py
Layer: 1 (Core - Deterministic Analytical)
Purpose: EQD2 conversion helper function

This is a utility function used by TCP models for biological dose normalization.
It's extracted here to avoid duplication across TCP model files.

Note: This may eventually be moved to rbgyanx.core.biological if needed
for use by other modules, but for now it's kept local to TCP models.
"""

from typing import Optional
import numpy as np


def convert_to_eqd2(
    dose: float,
    alpha_beta_ratio: float,
    dose_per_fraction: float,
    n_fractions: Optional[int] = None
) -> float:
    """
    Convert physical dose to EQD2 (Equivalent Dose in 2 Gy fractions).
    
    Parameters
    ----------
    dose : float
        Physical dose in Gy
    alpha_beta_ratio : float
        Alpha/beta ratio for the tissue (Gy)
    dose_per_fraction : float
        Dose per fraction in Gy
    n_fractions : int, optional
        Number of fractions (if not provided, calculated from dose/dose_per_fraction)
    
    Returns
    -------
    float
        EQD2 in Gy
    
    Notes
    -----
    EQD2 = D * (d + α/β) / (2 + α/β)
    
    where:
        D = total physical dose (Gy)
        d = dose per fraction (Gy)
        α/β = tissue-specific radiobiological parameter (Gy)
    """
    if np.isnan(dose) or dose <= 0:
        return np.nan
        
    if dose_per_fraction is None:
        if n_fractions is not None:
            dose_per_fraction = dose / n_fractions
        else:
            dose_per_fraction = 2.0
    
    eqd2 = dose * (alpha_beta_ratio + dose_per_fraction) / (alpha_beta_ratio + 2.0)
    return eqd2

