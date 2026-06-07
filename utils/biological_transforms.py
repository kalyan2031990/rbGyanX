"""
Biological Transformations for DVH Data
========================================

This module implements novel biological transformations that extend
conventional DVH-based radiobiological modeling.

Key Features:
1. Fractionation-Aware DVH (FDVH) - Converts physical DVH to BED-normalized DVH
2. Biological dose metrics preserving DVH structure
3. Compatible with all downstream TCP/NTCP models

Author: KB (rbGyanX Project)
License: MIT

NOTE: This module maintains backward compatibility. The core computational
class FractionationAwareDVH has been moved to rbgyanx.core.biological.transforms
as part of Phase 1 refactoring (3-layer architecture).
"""

# Backward compatibility: Import from new location
# Phase 1 refactoring: Core computation moved to rbgyanx.core.biological.transforms
from rbgyanx.core.biological.transforms import FractionationAwareDVH

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, Dict

# Re-export for backward compatibility
__all__ = ['FractionationAwareDVH', 'create_bed_dvh_report']


def create_bed_dvh_report(
    dvh_df: pd.DataFrame, 
    n_fractions: int, 
    total_dose: float, 
    alpha_beta: float = 10.0, 
    structure_name: str = 'Structure', 
    output_file: Optional[Path] = None
) -> Dict:
    """
    Generate comprehensive BED-DVH analysis report
    
    NOTE: This function includes file I/O (Excel export) and is kept in utils/
    for backward compatibility. The core computation (FractionationAwareDVH)
    is now in rbgyanx.core.biological.transforms.
    
    Parameters
    ----------
    dvh_df : pd.DataFrame
        Physical DVH
    n_fractions : int
        Number of fractions
    total_dose : float
        Total prescribed dose (Gy)
    alpha_beta : float, optional
        α/β ratio (default: 10 Gy)
    structure_name : str, optional
        Name of the structure
    output_file : Path, optional
        If provided, save report to Excel file
    
    Returns
    -------
    report : dict
        Comprehensive BED analysis
    """
    fdvh = FractionationAwareDVH(alpha_beta=alpha_beta)
    
    # Transform DVH
    bio_dvh = fdvh.transform_dvh(dvh_df, n_fractions, total_dose)
    
    # Calculate metrics
    metrics = fdvh.get_bed_metrics(dvh_df, n_fractions, total_dose)
    
    # Calculate EQD2
    eqd2_dvh = fdvh.calculate_eqd2(dvh_df, n_fractions, total_dose)
    
    report: Dict = {
        'structure': structure_name,
        'fractionation': {
            'n_fractions': n_fractions,
            'total_dose': total_dose,
            'dose_per_fraction': total_dose / n_fractions
        },
        'parameters': {
            'alpha_beta': alpha_beta
        },
        'bed_metrics': metrics,
        'bio_dvh': bio_dvh,
        'eqd2_dvh': eqd2_dvh
    }
    
    if output_file:
        output_path = Path(output_file)
        with pd.ExcelWriter(output_path) as writer:
            bio_dvh.to_excel(writer, sheet_name='BED_DVH', index=False)
            eqd2_dvh.to_excel(writer, sheet_name='EQD2_DVH', index=False)
            pd.DataFrame([metrics]).to_excel(writer, sheet_name='Metrics', index=False)
    
    return report


# Example usage and testing
if __name__ == '__main__':
    # Example: Standard fractionation vs hypofractionation comparison
    
    # Create sample DVH
    sample_dvh = pd.DataFrame({
        'Dose[Gy]': np.linspace(0, 70, 100),
        'Volume[%]': np.exp(-np.linspace(0, 70, 100) / 20) * 100
    })
    
    # Define fractionation schemes
    schemes = [
        {'name': 'Standard (2 Gy x 35)', 'n_fractions': 35, 'total_dose': 70},
        {'name': 'Hypofractionation (2.5 Gy x 28)', 'n_fractions': 28, 'total_dose': 70},
        {'name': 'SBRT (10 Gy x 5)', 'n_fractions': 5, 'total_dose': 50},
    ]
    
    # Compare schemes
    fdvh = FractionationAwareDVH(alpha_beta=10)
    comparison = fdvh.compare_fractionation_schemes(sample_dvh, schemes)
    
    print("Fractionation Scheme Comparison (α/β = 10 Gy):")
    print(comparison)
