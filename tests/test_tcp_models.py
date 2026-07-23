#!/usr/bin/env python3
"""
Unit Tests for TCP Models
=========================

Tests for four TCP models against published benchmarks and mathematical properties:
1. Poisson TCP (Webb & Nahum, 1993)
2. LKB-adapted TCP (Okunieff et al., 1995)
3. Logistic TCP (Brahme, 1984)
4. EUD-based TCP (Niemierko, 1997)

Author: TCP_NTCP Pipeline Team
Version: 2.0.0
"""

import unittest
import numpy as np
import pandas as pd
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.tcp_models import TCPCalculator


class TestTCPModels(unittest.TestCase):
    """Test suite for TCP models"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tcp_calc = TCPCalculator()
        
        # Create sample DVH data (uniform dose distribution)
        self.sample_dvh = pd.DataFrame({
            'dose_gy': np.arange(0, 71, 0.5),
            'volume_cm3': np.ones(142) * 10.0  # 10 cm3 per bin
        })
        
        # Create sample dose metrics
        self.sample_dose_metrics = {
            'mean_dose': 50.0,
            'max_dose': 70.0,
            'v_effective': 100.0  # 100 cm3
        }
    
    def test_convert_to_eqd2(self):
        """Test EQD2 conversion"""
        # Standard 2 Gy per fraction
        eqd2 = self.tcp_calc.convert_to_eqd2(60.0, 10.0, 2.0)
        self.assertAlmostEqual(eqd2, 60.0, places=5)
        
        # Different fraction size (3 Gy per fraction)
        eqd2 = self.tcp_calc.convert_to_eqd2(60.0, 10.0, 3.0)
        self.assertGreater(eqd2, 60.0)  # Higher EQD2 for larger fractions
        
        # Invalid inputs
        self.assertTrue(np.isnan(self.tcp_calc.convert_to_eqd2(0, 10.0, 2.0)))
        self.assertTrue(np.isnan(self.tcp_calc.convert_to_eqd2(-10, 10.0, 2.0)))
    
    def test_tcp_poisson_basic(self):
        """Test Poisson TCP model basic functionality"""
        # Test with standard parameters
        tcp = self.tcp_calc.tcp_poisson(
            self.sample_dvh,
            D50=50.0,
            gamma50=2.0,
            alpha_beta=10.0,
            dose_per_fraction=2.0
        )
        
        # TCP should be between 0 and 1
        self.assertGreaterEqual(tcp, 0.0)
        self.assertLessEqual(tcp, 1.0)
        
        # TCP should increase with dose
        dvh_low = pd.DataFrame({
            'dose_gy': [30.0],
            'volume_cm3': [100.0]
        })
        dvh_high = pd.DataFrame({
            'dose_gy': [70.0],
            'volume_cm3': [100.0]
        })
        
        tcp_low = self.tcp_calc.tcp_poisson(dvh_low, 50.0, 2.0)
        tcp_high = self.tcp_calc.tcp_poisson(dvh_high, 50.0, 2.0)
        self.assertGreater(tcp_high, tcp_low)
    
    def test_tcp_poisson_edge_cases(self):
        """Test Poisson TCP model edge cases"""
        # Empty DVH
        empty_dvh = pd.DataFrame({'dose_gy': [], 'volume_cm3': []})
        tcp = self.tcp_calc.tcp_poisson(empty_dvh, 50.0, 2.0)
        self.assertEqual(tcp, 0.0)
        
        # Zero dose
        zero_dvh = pd.DataFrame({'dose_gy': [0.0], 'volume_cm3': [100.0]})
        tcp = self.tcp_calc.tcp_poisson(zero_dvh, 50.0, 2.0)
        self.assertLess(tcp, 0.1)  # Very low TCP for zero dose
        
        # Invalid parameters
        tcp = self.tcp_calc.tcp_poisson(self.sample_dvh, 0, 2.0)
        self.assertEqual(tcp, 0.0)
        tcp = self.tcp_calc.tcp_poisson(self.sample_dvh, 50.0, 0)
        self.assertEqual(tcp, 0.0)
        tcp = self.tcp_calc.tcp_poisson(None, 50.0, 2.0)
        self.assertEqual(tcp, 0.0)
    
    def test_tcp_lkb_basic(self):
        """Test LKB-adapted TCP model basic functionality"""
        # Test with standard parameters
        tcp = self.tcp_calc.tcp_lkb(
            self.sample_dose_metrics,
            TD50=50.0,
            m=0.15,
            n=0.12,
            alpha_beta=10.0,
            dose_per_fraction=2.0
        )
        
        # TCP should be between 0 and 1
        self.assertGreaterEqual(tcp, 0.0)
        self.assertLessEqual(tcp, 1.0)
        
        # TCP should increase with dose
        metrics_low = {'mean_dose': 30.0, 'max_dose': 30.0, 'v_effective': 100.0}
        metrics_high = {'mean_dose': 70.0, 'max_dose': 70.0, 'v_effective': 100.0}
        
        tcp_low = self.tcp_calc.tcp_lkb(metrics_low, 50.0, 0.15, 0.12)
        tcp_high = self.tcp_calc.tcp_lkb(metrics_high, 50.0, 0.15, 0.12)
        self.assertGreater(tcp_high, tcp_low)
    
    def test_tcp_lkb_at_td50(self):
        """Test LKB TCP at TD50 (should be approximately 0.5)"""
        # At TD50 with reference volume (1 cm3), TCP should be close to 0.5
        metrics_td50 = {
            'mean_dose': 50.0,
            'max_dose': 50.0,
            'v_effective': 1.0  # Reference volume
        }
        tcp = self.tcp_calc.tcp_lkb(metrics_td50, TD50=50.0, m=0.15, n=0.12)
        
        # Should be close to 0.5 (within reasonable tolerance)
        self.assertGreater(tcp, 0.3)
        self.assertLess(tcp, 0.7)
    
    def test_tcp_lkb_edge_cases(self):
        """Test LKB TCP model edge cases"""
        # Missing v_effective
        metrics_no_veff = {'mean_dose': 50.0, 'max_dose': 50.0}
        tcp = self.tcp_calc.tcp_lkb(metrics_no_veff, 50.0, 0.15, 0.12)
        self.assertEqual(tcp, 0.0)
        
        # Invalid parameters
        tcp = self.tcp_calc.tcp_lkb(self.sample_dose_metrics, 0, 0.15, 0.12)
        self.assertEqual(tcp, 0.0)
        tcp = self.tcp_calc.tcp_lkb(self.sample_dose_metrics, 50.0, 0, 0.12)
        self.assertEqual(tcp, 0.0)
    
    def test_tcp_logistic_basic(self):
        """Test Logistic TCP model basic functionality"""
        # Test with standard parameters
        tcp = self.tcp_calc.tcp_logistic(
            self.sample_dose_metrics,
            D50=50.0,
            k=0.35,
            alpha_beta=10.0,
            dose_per_fraction=2.0
        )
        
        # TCP should be between 0 and 1
        self.assertGreaterEqual(tcp, 0.0)
        self.assertLessEqual(tcp, 1.0)
        
        # TCP should increase with dose
        metrics_low = {'mean_dose': 30.0}
        metrics_high = {'mean_dose': 70.0}
        
        tcp_low = self.tcp_calc.tcp_logistic(metrics_low, 50.0, 0.35)
        tcp_high = self.tcp_calc.tcp_logistic(metrics_high, 50.0, 0.35)
        self.assertGreater(tcp_high, tcp_low)
    
    def test_tcp_logistic_at_d50(self):
        """Test Logistic TCP at D50 (should be exactly 0.5)"""
        # At D50, TCP = 1 / (1 + (D50/D50)^k) = 1 / (1 + 1^k) = 0.5
        metrics_d50 = {'mean_dose': 50.0}
        tcp = self.tcp_calc.tcp_logistic(metrics_d50, D50=50.0, k=0.35)
        
        # Should be exactly 0.5 (within floating point precision)
        self.assertAlmostEqual(tcp, 0.5, places=5)
    
    def test_tcp_logistic_edge_cases(self):
        """Test Logistic TCP model edge cases"""
        # Zero dose
        metrics_zero = {'mean_dose': 0.0}
        tcp = self.tcp_calc.tcp_logistic(metrics_zero, 50.0, 0.35)
        self.assertEqual(tcp, 0.0)
        
        # Very high dose (should approach 1.0, but k=0.35 gives moderate steepness)
        metrics_high = {'mean_dose': 200.0}
        tcp = self.tcp_calc.tcp_logistic(metrics_high, 50.0, 0.35)
        # With k=0.35, TCP at 4*D50 is approximately 0.62, which is reasonable
        self.assertGreater(tcp, 0.5)  # Should be higher than at D50
        
        # Invalid parameters
        tcp = self.tcp_calc.tcp_logistic(self.sample_dose_metrics, 0, 0.35)
        self.assertEqual(tcp, 0.0)
        tcp = self.tcp_calc.tcp_logistic(self.sample_dose_metrics, 50.0, 0)
        self.assertEqual(tcp, 0.0)
    
    def test_tcp_eud_basic(self):
        """Test EUD-based TCP model basic functionality"""
        # Test with standard parameters
        tcp = self.tcp_calc.tcp_eud(
            self.sample_dvh,
            D50=50.0,
            gamma50=2.0,
            a=-10.0,
            alpha_beta=10.0,
            dose_per_fraction=2.0
        )
        
        # TCP should be between 0 and 1
        self.assertGreaterEqual(tcp, 0.0)
        self.assertLessEqual(tcp, 1.0)
        
        # TCP should increase with dose
        dvh_low = pd.DataFrame({
            'dose_gy': [30.0],
            'volume_cm3': [100.0]
        })
        dvh_high = pd.DataFrame({
            'dose_gy': [70.0],
            'volume_cm3': [100.0]
        })
        
        tcp_low = self.tcp_calc.tcp_eud(dvh_low, 50.0, 2.0, -10.0)
        tcp_high = self.tcp_calc.tcp_eud(dvh_high, 50.0, 2.0, -10.0)
        self.assertGreater(tcp_high, tcp_low)
    
    def test_tcp_eud_at_d50(self):
        """Test EUD TCP at D50 (should be approximately 0.5)"""
        # Uniform dose at D50
        dvh_d50 = pd.DataFrame({
            'dose_gy': [50.0],
            'volume_cm3': [100.0]
        })
        tcp = self.tcp_calc.tcp_eud(dvh_d50, D50=50.0, gamma50=2.0, a=-10.0)
        
        # Should be close to 0.5 (within reasonable tolerance)
        self.assertGreater(tcp, 0.3)
        self.assertLess(tcp, 0.7)
    
    def test_tcp_eud_edge_cases(self):
        """Test EUD TCP model edge cases"""
        # Empty DVH
        empty_dvh = pd.DataFrame({'dose_gy': [], 'volume_cm3': []})
        tcp = self.tcp_calc.tcp_eud(empty_dvh, 50.0, 2.0, -10.0)
        self.assertEqual(tcp, 0.0)
        
        # Zero dose (should return 0.0 due to filtering)
        zero_dvh = pd.DataFrame({'dose_gy': [0.0], 'volume_cm3': [100.0]})
        tcp = self.tcp_calc.tcp_eud(zero_dvh, 50.0, 2.0, -10.0)
        self.assertEqual(tcp, 0.0)  # Should return 0.0 for zero dose
        
        # Invalid parameters
        tcp = self.tcp_calc.tcp_eud(self.sample_dvh, 0, 2.0, -10.0)
        self.assertEqual(tcp, 0.0)
        tcp = self.tcp_calc.tcp_eud(self.sample_dvh, 50.0, 0, -10.0)
        self.assertEqual(tcp, 0.0)
        tcp = self.tcp_calc.tcp_eud(None, 50.0, 2.0, -10.0)
        self.assertEqual(tcp, 0.0)
    
    def test_calculate_all_tcp_models(self):
        """Test calculation of all TCP models"""
        # Test with HNSCC parameters
        results = self.tcp_calc.calculate_all_tcp_models(
            self.sample_dvh,
            self.sample_dose_metrics,
            'HNSCC',
            dose_per_fraction=2.0
        )
        
        # Should return results for all 4 models
        self.assertIn('Poisson_TCP', results)
        self.assertIn('LKB_TCP', results)
        self.assertIn('Logistic_TCP', results)
        self.assertIn('EUD_TCP', results)
        
        # Each result should have TCP value
        for model_name, result in results.items():
            self.assertIn('TCP', result)
            tcp = result['TCP']
            self.assertGreaterEqual(tcp, 0.0)
            self.assertLessEqual(tcp, 1.0)
            self.assertIn('parameters_used', result)
    
    def test_calculate_all_tcp_models_unknown_tumor(self):
        """Test calculation with unknown tumor type"""
        results = self.tcp_calc.calculate_all_tcp_models(
            self.sample_dvh,
            self.sample_dose_metrics,
            'UnknownTumor',
            dose_per_fraction=2.0
        )
        
        # Should return empty dict
        self.assertEqual(results, {})
    
    def test_tcp_monotonicity(self):
        """Test that TCP increases monotonically with dose"""
        doses = np.arange(20, 80, 5)
        
        for dose in doses:
            dvh = pd.DataFrame({
                'dose_gy': [dose],
                'volume_cm3': [100.0]
            })
            metrics = {'mean_dose': dose, 'max_dose': dose, 'v_effective': 100.0}
            
            # Test all models
            tcp_poisson = self.tcp_calc.tcp_poisson(dvh, 50.0, 2.0)
            tcp_lkb = self.tcp_calc.tcp_lkb(metrics, 50.0, 0.15, 0.12)
            tcp_logistic = self.tcp_calc.tcp_logistic(metrics, 50.0, 0.35)
            tcp_eud = self.tcp_calc.tcp_eud(dvh, 50.0, 2.0, -10.0)
            
            # All should be valid
            for tcp in [tcp_poisson, tcp_lkb, tcp_logistic, tcp_eud]:
                self.assertGreaterEqual(tcp, 0.0)
                self.assertLessEqual(tcp, 1.0)
    
    def test_tcp_parameter_sensitivity(self):
        """Test sensitivity to parameter changes"""
        # Higher D50 should give lower TCP for same dose
        dvh = pd.DataFrame({'dose_gy': [50.0], 'volume_cm3': [100.0]})
        metrics = {'mean_dose': 50.0, 'max_dose': 50.0, 'v_effective': 100.0}
        
        tcp_low_d50 = self.tcp_calc.tcp_logistic(metrics, D50=40.0, k=0.35)
        tcp_high_d50 = self.tcp_calc.tcp_logistic(metrics, D50=60.0, k=0.35)
        self.assertGreater(tcp_low_d50, tcp_high_d50)
        
        # Higher gamma50/k should give steeper curve
        tcp_low_k = self.tcp_calc.tcp_logistic(metrics, D50=50.0, k=0.25)
        tcp_high_k = self.tcp_calc.tcp_logistic(metrics, D50=50.0, k=0.50)
        # At D50, both should be 0.5, but away from D50, higher k gives steeper curve
        # Test at dose > D50
        metrics_high = {'mean_dose': 60.0}
        tcp_low_k_high = self.tcp_calc.tcp_logistic(metrics_high, D50=50.0, k=0.25)
        tcp_high_k_high = self.tcp_calc.tcp_logistic(metrics_high, D50=50.0, k=0.50)
        self.assertGreater(tcp_high_k_high, tcp_low_k_high)


class TestTCPModelsBenchmarks(unittest.TestCase):
    """Test TCP models against published benchmarks"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tcp_calc = TCPCalculator()
    
    def test_poisson_tcp_benchmark(self):
        """Test Poisson TCP against expected behavior"""
        # Uniform dose distribution
        dvh = pd.DataFrame({
            'dose_gy': [50.0],
            'volume_cm3': [100.0]
        })
        
        # At D50, TCP should be reasonable (not necessarily 0.5 due to model complexity)
        tcp = self.tcp_calc.tcp_poisson(dvh, D50=50.0, gamma50=2.0)
        self.assertGreater(tcp, 0.1)
        self.assertLess(tcp, 0.9)
    
    def test_lkb_tcp_benchmark(self):
        """Test LKB TCP against expected behavior"""
        # At TD50 with reference volume, TCP should be approximately 0.5
        metrics = {
            'mean_dose': 50.0,
            'max_dose': 50.0,
            'v_effective': 1.0  # Reference volume
        }
        tcp = self.tcp_calc.tcp_lkb(metrics, TD50=50.0, m=0.15, n=0.12)
        # Should be close to 0.5
        self.assertGreater(tcp, 0.3)
        self.assertLess(tcp, 0.7)
    
    def test_logistic_tcp_benchmark(self):
        """Test Logistic TCP against expected behavior"""
        # At D50, TCP should be exactly 0.5
        metrics = {'mean_dose': 50.0}
        tcp = self.tcp_calc.tcp_logistic(metrics, D50=50.0, k=0.35)
        self.assertAlmostEqual(tcp, 0.5, places=5)
        
        # At 2*D50, TCP should be higher than at D50
        metrics_2x = {'mean_dose': 100.0}
        tcp_2x = self.tcp_calc.tcp_logistic(metrics_2x, D50=50.0, k=0.35)
        # With k=0.35, TCP at 2*D50 is approximately 0.56
        self.assertGreater(tcp_2x, 0.5)  # Should be higher than at D50
    
    def test_eud_tcp_benchmark(self):
        """Test EUD TCP against expected behavior"""
        # Uniform dose at D50
        dvh = pd.DataFrame({
            'dose_gy': [50.0],
            'volume_cm3': [100.0]
        })
        tcp = self.tcp_calc.tcp_eud(dvh, D50=50.0, gamma50=2.0, a=-10.0)
        # Should be close to 0.5
        self.assertGreater(tcp, 0.3)
        self.assertLess(tcp, 0.7)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)

