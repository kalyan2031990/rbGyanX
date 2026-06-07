"""
Module: rbgyanx/core/tcp/logistic.py
Layer: 1 (Core - Deterministic Analytical)
Purpose: TCP calculation using Logistic model

Mathematical Formulation:
-------------------------
Logistic TCP Model (Brahme, 1984)

TCP = 1 / (1 + (D50/D_eqd2)^k)

where:
    D_eqd2 = dose in EQD2
    D50 = dose for 50% TCP (Gy)
    k = steepness parameter

References:
-----------
Brahme A (1984). Dosimetric precision requirements in radiation therapy.
Acta Radiol Oncol. 23(5):379-391.
"""

from typing import Dict, Optional
import numpy as np
from rbgyanx.core.tcp._eqd2 import convert_to_eqd2


def calculate_tcp_logistic(
    dose_metrics: Dict[str, float],
    D50: float,
    k: float,
    alpha_beta: float = 10.0,
    dose_per_fraction: float = 2.0
) -> float:
    """
    Calculate TCP using Logistic model.
    
    This function implements the logistic TCP model using dose metrics,
    matching the original TCPCalculator.tcp_logistic implementation.
    
    Parameters
    ----------
    dose_metrics : Dict[str, float]
        Dictionary containing dose metrics. Must include:
        - 'mean_dose': mean dose (Gy) or 'max_dose': maximum dose (Gy)
    D50 : float
        Dose for 50% TCP (Gy)
    k : float
        Steepness parameter (dimensionless, typically 0.3-0.5)
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
    - Typically uses mean dose or maximum dose
    - Uses EQD2 conversion for dose normalization
    - Original implementation from utils.tcp_models.TCPCalculator.tcp_logistic
    """
    if D50 <= 0:
        raise ValueError("D50 must be positive")
    if k <= 0:
        raise ValueError("k must be positive")
    dose = dose_metrics.get("mean_dose", dose_metrics.get("max_dose", 0))
    if dose <= 0 and "mean_dose" not in dose_metrics and "max_dose" not in dose_metrics:
        raise ValueError("dose_metrics must include 'mean_dose' or 'max_dose'")
    if dose <= 0:
        return 0.0
    
    try:
        # Convert to EQD2
        dose_eqd2 = convert_to_eqd2(dose, alpha_beta, dose_per_fraction)
        
        # Logistic function: TCP = 1 / (1 + (D50/D)^k)
        # For TCP, higher dose = higher TCP, so use D/D50
        ratio = D50 / dose_eqd2
        tcp = 1.0 / (1.0 + np.power(ratio, k))
        
        # Clip to valid range
        tcp = np.clip(tcp, 1e-15, 1.0 - 1e-15)
        return float(tcp)
        
    except (OverflowError, ZeroDivisionError, ValueError):
        return 0.0 if dose < D50 else 1.0


__all__ = ['calculate_tcp_logistic']
