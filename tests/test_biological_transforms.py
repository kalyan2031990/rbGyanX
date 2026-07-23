"""
Unit tests for biological transforms module

Tests for rbgyanx.core.biological.transforms (Phase 1 refactoring)
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rbgyanx.core.biological.transforms import FractionationAwareDVH


class TestFractionationAwareDVH:
    """Test suite for FractionationAwareDVH class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.sample_dvh = pd.DataFrame({
            'Dose[Gy]': np.linspace(0, 70, 100),
            'Volume[%]': np.exp(-np.linspace(0, 70, 100) / 20) * 100
        })
        
        self.simple_dvh = pd.DataFrame({
            'Dose[Gy]': [0, 20, 40, 60],
            'Volume[%]': [100, 80, 50, 20]
        })
    
    def test_initialization_default(self):
        """Test default initialization"""
        fdvh = FractionationAwareDVH()
        assert fdvh.alpha_beta == 10.0
        assert fdvh.tissue_type == 'tumor'
    
    def test_initialization_custom_alpha_beta(self):
        """Test initialization with custom alpha/beta"""
        fdvh = FractionationAwareDVH(alpha_beta=3.0)
        assert fdvh.alpha_beta == 3.0
    
    def test_initialization_tissue_type(self):
        """Test initialization with tissue type"""
        fdvh_late = FractionationAwareDVH(tissue_type='late')
        assert fdvh_late.alpha_beta == 3.0
        
        fdvh_tumor = FractionationAwareDVH(tissue_type='tumor')
        assert fdvh_tumor.alpha_beta == 10.0
    
    def test_transform_dvh_basic(self):
        """Test basic DVH transformation to BED"""
        fdvh = FractionationAwareDVH(alpha_beta=10.0)
        result = fdvh.transform_dvh(
            self.simple_dvh, 
            n_fractions=30, 
            total_dose=60
        )
        
        # Check output structure
        assert isinstance(result, pd.DataFrame)
        assert 'BED[Gy]' in result.columns
        assert 'Volume[%]' in result.columns
        assert 'PhysicalDose[Gy]' in result.columns
        assert 'DosePerFraction[Gy]' in result.columns
        
        # Check shape
        assert result.shape[0] == 4
        assert result.shape[1] == 4
        
        # Zero physical dose → BED 0; positive doses → positive BED
        pos = result["PhysicalDose[Gy]"] > 0
        assert (result.loc[pos, "BED[Gy]"] > 0).all()
        assert (result.loc[~pos, "BED[Gy]"] == 0).all()
        
        # Check that BED is sorted
        assert result['BED[Gy]'].is_monotonic_increasing
    
    def test_transform_dvh_dose_per_fraction(self):
        """Test transformation with dose_per_fraction parameter"""
        fdvh = FractionationAwareDVH(alpha_beta=10.0)
        result = fdvh.transform_dvh(
            self.simple_dvh,
            n_fractions=30,
            dose_per_fraction=2.0
        )
        
        assert isinstance(result, pd.DataFrame)
        assert 'BED[Gy]' in result.columns
    
    def test_transform_dvh_error_missing_params(self):
        """Test that error is raised when both parameters missing"""
        fdvh = FractionationAwareDVH()
        with pytest.raises(ValueError, match="Must provide either"):
            fdvh.transform_dvh(self.simple_dvh, n_fractions=30)
    
    def test_transform_dvh_column_variants(self):
        """Test that function handles different column name variants"""
        dvh_variant = pd.DataFrame({
            'dose_gy': [0, 20, 40, 60],
            'volume_percent': [100, 80, 50, 20]
        })
        
        fdvh = FractionationAwareDVH()
        result = fdvh.transform_dvh(dvh_variant, n_fractions=30, total_dose=60)
        
        assert isinstance(result, pd.DataFrame)
        assert 'BED[Gy]' in result.columns
    
    def test_calculate_eqd2_basic(self):
        """Test basic EQD2 calculation"""
        fdvh = FractionationAwareDVH(alpha_beta=10.0)
        result = fdvh.calculate_eqd2(
            self.simple_dvh,
            n_fractions=30,
            total_dose=60
        )
        
        # Check output structure
        assert isinstance(result, pd.DataFrame)
        assert 'EQD2[Gy]' in result.columns
        assert 'Volume[%]' in result.columns
        assert 'PhysicalDose[Gy]' in result.columns
        
        pos = result["PhysicalDose[Gy]"] > 0
        assert (result.loc[pos, "EQD2[Gy]"] > 0).all()
    
    def test_get_bed_metrics_basic(self):
        """Test basic BED metrics calculation"""
        fdvh = FractionationAwareDVH(alpha_beta=10.0)
        metrics = fdvh.get_bed_metrics(
            self.simple_dvh,
            n_fractions=30,
            total_dose=60
        )
        
        # Check output structure
        assert isinstance(metrics, dict)
        assert 'BED_mean' in metrics
        assert 'BED_max' in metrics
        assert 'BED_min' in metrics
        assert 'alpha_beta_used' in metrics
        assert 'n_fractions' in metrics
        
        # Check that metrics are reasonable
        assert metrics['BED_max'] > metrics['BED_mean']
        assert metrics['BED_mean'] > metrics['BED_min']
        assert metrics['alpha_beta_used'] == 10.0
        assert metrics['n_fractions'] == 30.0
    
    def test_compare_fractionation_schemes(self):
        """Test fractionation scheme comparison"""
        fdvh = FractionationAwareDVH(alpha_beta=10.0)
        
        schemes = [
            {'name': 'Standard', 'n_fractions': 35, 'total_dose': 70},
            {'name': 'Hypofraction', 'n_fractions': 28, 'total_dose': 70}
        ]
        
        result = fdvh.compare_fractionation_schemes(self.simple_dvh, schemes)
        
        # Check output structure
        assert isinstance(result, pd.DataFrame)
        assert result.shape[0] == 2  # Two schemes
        assert 'scheme_name' in result.columns
        assert 'BED_mean' in result.columns
    
    def test_numerical_equivalence_standard_case(self):
        """Test numerical equivalence for standard fractionation"""
        fdvh = FractionationAwareDVH(alpha_beta=10.0)
        
        # Standard: 2 Gy x 30 = 60 Gy total
        result = fdvh.transform_dvh(
            self.simple_dvh,
            n_fractions=30,
            total_dose=60
        )
        
        # For 2 Gy per fraction, BED should be close to total dose
        # BED = n * d * (1 + d/alpha_beta) = 30 * 2 * (1 + 2/10) = 60 * 1.2 = 72
        dose_per_fraction = 60 / 30  # 2 Gy
        expected_bed_per_bin = 30 * (60 / 30) * (1 + (60 / 30) / 10.0)
        
        # Check approximate equivalence (allowing for bin-by-bin variation)
        assert np.allclose(result['BED[Gy]'].mean(), expected_bed_per_bin * 0.5, rtol=0.1)
    
    def test_backward_compatibility_import(self):
        """Test that old import path still works"""
        from utils.biological_transforms import FractionationAwareDVH as OldImport
        from rbgyanx.core.biological.transforms import FractionationAwareDVH as NewImport
        
        # Both should be the same class
        assert OldImport is NewImport
        
        # Both should work identically
        fdvh_old = OldImport(alpha_beta=10.0)
        fdvh_new = NewImport(alpha_beta=10.0)
        
        result_old = fdvh_old.transform_dvh(self.simple_dvh, n_fractions=30, total_dose=60)
        result_new = fdvh_new.transform_dvh(self.simple_dvh, n_fractions=30, total_dose=60)
        
        pd.testing.assert_frame_equal(result_old, result_new)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

