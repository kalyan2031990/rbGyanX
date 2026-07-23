"""
Module: rbgyanx/core/tcp/poisson.py
Layer: 1 (Core - Deterministic Analytical)
Purpose: TCP calculation using Poisson model

Mathematical Formulation:
-------------------------
Poisson TCP Model (Webb & Nahum, 1993)

Based on Poisson statistics for cell survival and tumor control.
TCP = exp(-N0 * exp(-alpha*D - beta*D^2))

where:
    N0 = initial clonogen number
    alpha, beta = LQ model parameters
    D = dose

For DVH-based calculation:
    TCP_i = exp(-N0 * S_i * (V_i / V_total))
    TCP = product of TCP_i weighted by volume

where:
    S_i = exp(-alpha*D_i - beta*D_i^2) (survival fraction)
    V_i = volume of dose bin i
    V_total = total volume

References:
-----------
Webb S, Nahum AE (1993). A model for calculating tumour control probability
including the effects of inhomogeneous distributions of dose and clonogenic
cell density. Phys Med Biol. 38(6):653-666.
"""

from typing import Optional
import numpy as np
import pandas as pd

from rbgyanx.core.dvh_columns import normalize_dvh_columns


def calculate_tcp_poisson(
    dvh: pd.DataFrame,
    D50: float,
    gamma50: float,
    alpha_beta: float = 10.0,
    dose_per_fraction: float = 2.0
) -> float:
    """
    Calculate TCP using Poisson model (LQ-based implementation).
    
    This function implements the Poisson TCP model using Linear-Quadratic (LQ)
    cell survival and relative volume weighting, matching the original
    TCPCalculator.tcp_poisson implementation.
    
    Parameters
    ----------
    dvh : pd.DataFrame
        Differential DVH with columns 'dose_gy' and 'volume_cm3'
        Dose values should be in Gy, volume in cm³
    D50 : float
        Dose for 50% TCP (Gy)
    gamma50 : float
        Normalized dose-response gradient at D50 (dimensionless)
    alpha_beta : float, optional
        α/β ratio for biological normalization (Gy, default: 10.0)
    dose_per_fraction : float, optional
        Dose per fraction for biological normalization (Gy, default: 2.0)
        Note: Currently not used in calculation, kept for interface compatibility
    
    Returns
    -------
    float
        TCP value (0-1)
    
    Raises
    ------
    ValueError
        If required columns not found in DVH
    
    Notes
    -----
    - Assumes photon therapy
    - Uses LQ model: S = exp(-alpha*D - beta*D^2)
    - Alpha and beta are derived from D50 and gamma50
    - Original implementation from utils.tcp_models.TCPCalculator.tcp_poisson
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
        
        # Calculate alpha and beta from D50 and gamma50
        # gamma50 = dTCP/dD at D50, related to alpha and beta
        # Approximate: alpha = gamma50 / (D50 * ln(2))
        alpha = gamma50 / (D50 * np.log(2))  # Approximate alpha from gamma50
        beta = alpha / alpha_beta  # Beta from alpha/beta ratio
        
        # Calculate survival for each dose bin using LQ model
        # S = exp(-alpha*D - beta*D^2)
        survivals = np.exp(-alpha * doses - beta * doses * doses)
        
        # Estimate initial clonogen number from D50 condition
        # At D50: 0.5 = exp(-N0 * S(D50))
        # Therefore: N0 = ln(2) / S(D50)
        S_D50 = np.exp(-alpha * D50 - beta * D50 * D50)
        N0 = np.log(2) / S_D50
        
        # Calculate TCP for each voxel/bin
        # TCP_i = exp(-N0 * S_i * (V_i / V_total))
        # Overall TCP = product of TCP_i weighted by volume
        log_tcp_terms = -N0 * survivals * rel_volumes
        log_tcp = np.sum(log_tcp_terms)
        tcp = np.exp(log_tcp)
        
        # Clip to valid range
        tcp = np.clip(tcp, 1e-15, 1.0 - 1e-15)
        return float(tcp)
        
    except ValueError:
        raise
    except (OverflowError, ZeroDivisionError):
        return 0.0


__all__ = ['calculate_tcp_poisson']
