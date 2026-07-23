"""
Module: rbgyanx/core/biological/transforms.py
Layer: 1 (Core - Deterministic Analytical)
Purpose: Biological dose transformations (BED, EQD2, FDVH)

Allowed Dependencies:
- numpy, scipy, pandas
- Standard library

Forbidden Dependencies:
- UI frameworks (tkinter, PyQt, matplotlib.pyplot)
- AI/ML inference engines
- Mode controllers
- File I/O beyond data structures

Assumptions:
- All transformations assume photon therapy unless stated
- Parameters must be pre-validated by caller
- No applicability checking at this layer

Mathematical Formulation:
-------------------------
BED (Biologically Effective Dose):
    BED = n · d · (1 + d / (α/β))

EQD2 (Equivalent Dose in 2 Gy fractions):
    EQD2 = D · ((d + α/β) / (2 + α/β))

where:
    n = number of fractions
    d = dose per fraction (Gy)
    D = total dose (Gy)
    α/β = tissue-specific radiobiological parameter (Gy)

References:
-----------
Fowler JF (1989). Br J Radiol. 62(740):679-694.
McMahon SJ (2019). Phys Med Biol. 64(1):01TR01.
"""

from typing import Optional, Dict, List
import numpy as np
import pandas as pd


class FractionationAwareDVH:
    """
    Fractionation-Aware DVH (FDVH) Transformation
    
    Converts physical dose-volume histogram to biologically effective dose (BED)
    normalized histogram while preserving the DVH structure.
    
    Mathematical Formulation:
    -------------------------
    For each DVH dose bin i with dose d_i:
    
        BED_i = n · d_i · (1 + d_i / (α/β))
    
    where:
        n = number of fractions
        d_i = dose per fraction for bin i
        α/β = tissue-specific radiobiological parameter
    
    This enables:
    - Hypofractionation modeling
    - SBRT/SRS evaluation
    - Re-irradiation assessment
    - Cross-fractionation scheme comparison
    
    Examples
    --------
    >>> fdvh = FractionationAwareDVH(alpha_beta=10)
    >>> bio_dvh = fdvh.transform_dvh(
    ...     dvh_df=physical_dvh,
    ...     n_fractions=30,
    ...     total_dose=60  # Gy
    ... )
    
    References
    ----------
    Fowler JF (1989). Br J Radiol. 62(740):679-694.
    McMahon SJ (2019). Phys Med Biol. 64(1):01TR01.
    """
    
    def __init__(self, alpha_beta: float = 10.0, tissue_type: str = 'tumor') -> None:
        """
        Initialize FDVH transformer
        
        Parameters
        ----------
        alpha_beta : float, optional
            α/β ratio in Gy (default: 10 for tumor, 3 for late-responding tissue)
        tissue_type : str, optional
            'tumor', 'acute', 'late', or 'early' (sets default α/β)
        """
        _tissue_defaults: Dict[str, float] = {
            "tumor": 10.0,
            "acute": 10.0,
            "late": 3.0,
            "early": 10.0,
        }
        if tissue_type in _tissue_defaults and alpha_beta == 10.0:
            self.alpha_beta = _tissue_defaults[tissue_type]
        else:
            self.alpha_beta = float(alpha_beta)
        self.tissue_type = tissue_type
    
    def transform_dvh(
        self, 
        dvh_df: pd.DataFrame, 
        n_fractions: int, 
        total_dose: Optional[float] = None, 
        dose_per_fraction: Optional[float] = None
    ) -> pd.DataFrame:
        """
        Transform physical DVH to BED-normalized DVH
        
        Parameters
        ----------
        dvh_df : pd.DataFrame
            Physical DVH with columns ['Dose[Gy]', 'Volume[%]'] or variants
        n_fractions : int
            Number of fractions
        total_dose : float, optional
            Total prescribed dose (Gy). Either total_dose OR dose_per_fraction required.
        dose_per_fraction : float, optional
            Dose per fraction (Gy). Either total_dose OR dose_per_fraction required.
        
        Returns
        -------
        bio_dvh : pd.DataFrame
            Biological DVH with columns ['BED[Gy]', 'Volume[%]', 'PhysicalDose[Gy]', 'DosePerFraction[Gy]']
        
        Raises
        ------
        ValueError
            If neither total_dose nor dose_per_fraction provided
            If required columns not found in dvh_df
        """
        if total_dose is None and dose_per_fraction is None:
            raise ValueError("Must provide either total_dose or dose_per_fraction")
        
        # Calculate dose per fraction if not provided
        if dose_per_fraction is None:
            dose_per_fraction = total_dose / n_fractions  # type: ignore
        elif total_dose is None:
            total_dose = dose_per_fraction * n_fractions
        
        # Extract physical doses from DVH
        # Handle different column name formats
        dose_col: Optional[str] = None
        vol_col: Optional[str] = None
        
        for col in dvh_df.columns:
            if 'dose' in col.lower() and 'gy' in col.lower():
                dose_col = col
            if 'volume' in col.lower() and '%' in col.lower():
                vol_col = col
        
        if dose_col is None:
            # Try alternative names
            if 'Dose[Gy]' in dvh_df.columns:
                dose_col = 'Dose[Gy]'
            elif 'dose_gy' in dvh_df.columns:
                dose_col = 'dose_gy'
            else:
                raise ValueError("Could not find dose column in DVH DataFrame")
        
        if vol_col is None:
            if 'Volume[%]' in dvh_df.columns:
                vol_col = 'Volume[%]'
            elif 'volume_percent' in dvh_df.columns:
                vol_col = 'volume_percent'
            else:
                raise ValueError("Could not find volume column in DVH DataFrame")
        
        physical_doses = dvh_df[dose_col].values
        volumes = dvh_df[vol_col].values
        
        # Calculate dose per fraction for each DVH bin
        # Assumption: DVH bins represent cumulative dose distribution
        # For cumulative DVH, we need to convert to dose per fraction
        # If DVH is already per-fraction, use as-is; otherwise divide by n_fractions
        d_i = physical_doses / n_fractions
        
        # Calculate BED for each bin using LQ formula
        # BED = n · d · (1 + d/(α/β))
        bed_values = n_fractions * d_i * (1 + d_i / self.alpha_beta)
        
        # Create biological DVH DataFrame
        bio_dvh = pd.DataFrame({
            'BED[Gy]': bed_values,
            'Volume[%]': volumes,
            'PhysicalDose[Gy]': physical_doses,
            'DosePerFraction[Gy]': d_i
        })
        
        # Sort by BED (maintain monotonicity)
        bio_dvh = bio_dvh.sort_values('BED[Gy]').reset_index(drop=True)
        
        return bio_dvh
    
    def calculate_eqd2(
        self, 
        dvh_df: pd.DataFrame, 
        n_fractions: int, 
        total_dose: Optional[float] = None, 
        dose_per_fraction: Optional[float] = None
    ) -> pd.DataFrame:
        """
        Calculate EQD2 (Equivalent Dose in 2 Gy fractions) for DVH
        
        EQD2 = D · ((d + α/β) / (2 + α/β))
        
        where:
            D = total dose
            d = dose per fraction
        
        Parameters
        ----------
        dvh_df : pd.DataFrame
            Physical DVH
        n_fractions : int
            Number of fractions
        total_dose : float, optional
            Total dose (Gy)
        dose_per_fraction : float, optional
            Dose per fraction (Gy)
        
        Returns
        -------
        eqd2_dvh : pd.DataFrame
            DVH with EQD2-normalized doses
        
        Raises
        ------
        ValueError
            If neither total_dose nor dose_per_fraction provided
            If required columns not found in dvh_df
        """
        if dose_per_fraction is None:
            if total_dose is None:
                raise ValueError("Must provide either total_dose or dose_per_fraction")
            dose_per_fraction = total_dose / n_fractions
        
        # Find dose column
        dose_col: Optional[str] = None
        vol_col: Optional[str] = None
        
        for col in dvh_df.columns:
            if 'dose' in col.lower() and 'gy' in col.lower():
                dose_col = col
            if 'volume' in col.lower() and '%' in col.lower():
                vol_col = col
        
        if dose_col is None:
            if 'Dose[Gy]' in dvh_df.columns:
                dose_col = 'Dose[Gy]'
            elif 'dose_gy' in dvh_df.columns:
                dose_col = 'dose_gy'
            else:
                raise ValueError("Could not find dose column in DVH DataFrame")
        
        if vol_col is None:
            if 'Volume[%]' in dvh_df.columns:
                vol_col = 'Volume[%]'
            elif 'volume_percent' in dvh_df.columns:
                vol_col = 'volume_percent'
            else:
                raise ValueError("Could not find volume column in DVH DataFrame")
        
        physical_doses = dvh_df[dose_col].values
        d_i = physical_doses / n_fractions
        
        # EQD2 = D · ((d + α/β) / (2 + α/β))
        eqd2_values = physical_doses * (
            (d_i + self.alpha_beta) / (2 + self.alpha_beta)
        )
        
        eqd2_dvh = pd.DataFrame({
            'EQD2[Gy]': eqd2_values,
            'Volume[%]': dvh_df[vol_col].values,
            'PhysicalDose[Gy]': physical_doses
        })
        
        return eqd2_dvh
    
    def get_bed_metrics(
        self, 
        dvh_df: pd.DataFrame, 
        n_fractions: int, 
        total_dose: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate BED-based dose metrics from DVH
        
        Parameters
        ----------
        dvh_df : pd.DataFrame
            Physical DVH
        n_fractions : int
            Number of fractions
        total_dose : float, optional
            Total dose (Gy)
        
        Returns
        -------
        metrics : Dict[str, float]
            BED-based metrics including:
            - BED_mean: Mean BED (weighted average)
            - BED_max: Maximum BED
            - BED_min: Minimum BED
            - alpha_beta_used: α/β ratio used
            - n_fractions: Number of fractions
        """
        bio_dvh = self.transform_dvh(dvh_df, n_fractions, total_dose)
        
        # Calculate cumulative DVH from differential
        bed_values = bio_dvh['BED[Gy]'].values
        volumes = bio_dvh['Volume[%]'].values
        
        # Mean BED (weighted average)
        bed_mean = np.average(bed_values, weights=volumes)
        
        # Max BED
        bed_max = float(bed_values.max())
        
        # Min BED
        bed_min = float(bed_values.min())
        
        metrics: Dict[str, float] = {
            'BED_mean': float(bed_mean),
            'BED_max': bed_max,
            'BED_min': bed_min,
            'alpha_beta_used': self.alpha_beta,
            'n_fractions': float(n_fractions)
        }
        
        return metrics
    
    def compare_fractionation_schemes(
        self, 
        dvh_df: pd.DataFrame, 
        schemes: List[Dict[str, float]]
    ) -> pd.DataFrame:
        """
        Compare multiple fractionation schemes using FDVH
        
        Parameters
        ----------
        dvh_df : pd.DataFrame
            Physical DVH
        schemes : List[Dict[str, float]]
            Each dict: {'name': str, 'n_fractions': int, 'total_dose': float}
        
        Returns
        -------
        comparison_df : pd.DataFrame
            Comparative BED metrics for each scheme
        """
        results: List[Dict[str, float]] = []
        
        for scheme in schemes:
            metrics = self.get_bed_metrics(
                dvh_df,
                n_fractions=int(scheme['n_fractions']),
                total_dose=scheme['total_dose']
            )
            
            metrics['scheme_name'] = scheme['name']  # type: ignore
            metrics['n_fractions'] = scheme['n_fractions']  # type: ignore
            metrics['total_dose'] = scheme['total_dose']  # type: ignore
            
            results.append(metrics)  # type: ignore
        
        return pd.DataFrame(results)


__all__ = ['FractionationAwareDVH']

