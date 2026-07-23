"""
Module: rbgyanx/core/tcp/lkb.py
Layer: 1 (Core - Deterministic Analytical)
Purpose: TCP calculation using LKB-adapted model

Mathematical Formulation:
-------------------------
LKB-adapted TCP Model (Okunieff et al., 1995)

Uses Lyman-Kutcher-Burman effective volume concept adapted for TCP:

TCP = Φ((D_eqd2 - TD50_eff) / (m · TD50_eff))

where:
    D_eqd2 = effective dose in EQD2
    TD50_eff = effective TD50 based on volume
    TD50_eff = TD50 * (V_ref / V_eff)^n
    m = steepness parameter
    Φ = cumulative normal distribution (probit)

References:
-----------
Okunieff P, Morgan D, Niemierko A, Suit HD (1995). Radiation dose-response
of human tumors. Int J Radiat Oncol Biol Phys. 32(4):1227-1237.

Lyman JT (1985). Complication probability as assessed from dose-volume
histograms. Radiat Res. 104(2S):S13-S19.
"""

from typing import Dict, Optional
import numpy as np
from scipy.stats import norm
from rbgyanx.core.tcp._eqd2 import convert_to_eqd2


def calculate_tcp_lkb(
    dose_metrics: Dict[str, float],
    TD50: float,
    m: float,
    n: float,
    alpha_beta: float = 10.0,
    dose_per_fraction: float = 2.0
) -> float:
    """
    Calculate TCP using LKB-adapted model.
    
    This function implements the Lyman-Kutcher-Burman model adapted for TCP,
    using effective volume and dose metrics, matching the original
    TCPCalculator.tcp_lkb implementation.
    
    Parameters
    ----------
    dose_metrics : Dict[str, float]
        Dictionary containing dose metrics. Must include:
        - 'v_effective': effective volume (cm³)
        - 'max_dose': maximum dose (Gy) or 'mean_dose': mean dose (Gy)
    TD50 : float
        Dose for 50% TCP at reference volume (Gy)
    m : float
        Steepness parameter (dimensionless, typically 0.1-0.2)
    n : float
        Volume effect parameter (0=serial, 1=parallel, typically 0.1-0.2 for TCP)
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
    - Requires pre-calculated effective volume (v_effective in cm³)
    - Uses EQD2 conversion for dose normalization
    - Original implementation from utils.tcp_models.TCPCalculator.tcp_lkb
    """
    if TD50 <= 0:
        raise ValueError("TD50 must be positive")
    if m <= 0:
        raise ValueError("m must be positive")
    if "v_effective" not in dose_metrics:
        raise ValueError("dose_metrics must include 'v_effective'")
    v_eff = dose_metrics["v_effective"]
    if np.isnan(v_eff) or v_eff <= 0:
        raise ValueError("v_effective must be positive")
    if 1.0 < v_eff <= 10.0:
        raise ValueError("v_effective must be in range (0, 1]")
    max_dose = dose_metrics.get("max_dose", dose_metrics.get("mean_dose", 0))
    if max_dose <= 0:
        return 0.0
    
    try:
        # Convert to EQD2
        max_dose_eqd2 = convert_to_eqd2(max_dose, alpha_beta, dose_per_fraction)
        
        # Calculate effective TD50 based on volume
        # TD50_eff = TD50 * (V_ref / V_eff)^n
        # For tumors, use reference volume of 1 cm³
        v_ref = 1.0
        if n != 0:
            td_veff_50 = TD50 * np.power(v_ref / v_eff, n)
        else:
            td_veff_50 = TD50
        
        # Calculate t parameter
        # At TD50 with reference volume, t should be 0 (giving TCP = 0.5)
        t = (max_dose_eqd2 - td_veff_50) / (m * td_veff_50)
        
        # Apply probit function (cumulative normal distribution)
        # For TCP, higher dose = higher TCP, so use positive t
        tcp = norm.cdf(t)
        
        # Clip to valid range
        tcp = np.clip(tcp, 1e-15, 1.0 - 1e-15)
        return float(tcp)
        
    except (OverflowError, ZeroDivisionError, ValueError):
        return 0.0 if max_dose < TD50 else 1.0


__all__ = ['calculate_tcp_lkb']
