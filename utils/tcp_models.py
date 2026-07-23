#!/usr/bin/env python3
"""
TCP Models for Tumor Control Probability
========================================

Implementation of four literature-based TCP models:
1. Poisson TCP (Webb & Nahum, 1993)
2. LKB-adapted TCP (Okunieff et al., 1995)
3. Logistic TCP (Brahme, 1984)
4. EUD-based TCP (Niemierko, 1997)

Author: TCP_NTCP Pipeline Team
Version: 2.0.0

NOTE: Phase 1B.2 Refactoring - Core computation moved to rbgyanx.core.tcp
This module maintains backward compatibility by delegating to core functions.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.special import gamma
from typing import Dict, Optional, Union
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Try to import yaml for config loading
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    print("Warning: PyYAML not available. Install with: pip install pyyaml")

# Backward compatibility: Import from new location
# Phase 1B.2 refactoring: Core computation moved to rbgyanx.core.tcp
from rbgyanx.core.tcp.poisson import calculate_tcp_poisson
from rbgyanx.core.tcp.lkb import calculate_tcp_lkb
from rbgyanx.core.tcp.logistic import calculate_tcp_logistic
from rbgyanx.core.tcp.eud import calculate_tcp_eud
from rbgyanx.core.tcp._eqd2 import convert_to_eqd2


class TCPCalculator:
    """Calculate TCP using published model equations
    
    NOTE: Phase 1B.2 Refactoring - This class now delegates to core functions
    in rbgyanx.core.tcp while maintaining the same interface for backward compatibility.
    """
    
    def __init__(self, config_file=None):
        """
        Initialize TCP calculator.
        
        Parameters
        ----------
        config_file : str or Path, optional
            Path to YAML configuration file. If None, uses default parameters.
        """
        # Try to load parameters from YAML file
        if config_file is None:
            config_file = Path(__file__).parent.parent / 'config' / 'tcp_parameters.yaml'
        
        self.literature_params = self._load_parameters(config_file)
    
    def _load_parameters(self, config_file):
        """
        Load parameters from YAML file or use defaults.
        
        Parameters
        ----------
        config_file : str or Path
            Path to YAML configuration file
            
        Returns
        -------
        dict
            Dictionary of parameters by tumor type
        """
        # Default parameters (fallback if YAML not available)
        default_params = {
            'HNSCC': {  # Head and Neck Squamous Cell Carcinoma
                'Poisson_TCP': {'D50': 50.0, 'gamma50': 2.0, 'alpha_beta': 10},
                'LKB_TCP': {'TD50': 50.0, 'm': 0.15, 'n': 0.12, 'alpha_beta': 10},
                'Logistic_TCP': {'D50': 50.0, 'k': 0.35, 'alpha_beta': 10},
                'EUD_TCP': {'D50': 50.0, 'gamma50': 2.0, 'a': -10, 'alpha_beta': 10}
            },
            'Prostate': {
                'Poisson_TCP': {'D50': 70.0, 'gamma50': 1.5, 'alpha_beta': 1.5},
                'LKB_TCP': {'TD50': 70.0, 'm': 0.12, 'n': 0.10, 'alpha_beta': 1.5},
                'Logistic_TCP': {'D50': 70.0, 'k': 0.30, 'alpha_beta': 1.5},
                'EUD_TCP': {'D50': 70.0, 'gamma50': 1.5, 'a': -10, 'alpha_beta': 1.5}
            },
            'Lung': {
                'Poisson_TCP': {'D50': 60.0, 'gamma50': 1.8, 'alpha_beta': 10},
                'LKB_TCP': {'TD50': 60.0, 'm': 0.18, 'n': 0.15, 'alpha_beta': 10},
                'Logistic_TCP': {'D50': 60.0, 'k': 0.40, 'alpha_beta': 10},
                'EUD_TCP': {'D50': 60.0, 'gamma50': 1.8, 'a': -10, 'alpha_beta': 10}
            }
        }
        
        # Try to load from YAML file
        config_path = Path(config_file)
        if YAML_AVAILABLE and config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    yaml_params = yaml.safe_load(f)
                    if yaml_params:
                        # Remove 'reference' keys if present (they're just documentation)
                        cleaned_params = {}
                        for tumor_type, models in yaml_params.items():
                            if isinstance(models, dict):
                                cleaned_models = {}
                                for model_name, params in models.items():
                                    if isinstance(params, dict) and 'reference' not in model_name:
                                        # Remove 'reference' from individual model params
                                        cleaned_model_params = {
                                            k: v for k, v in params.items() 
                                            if k != 'reference'
                                        }
                                        cleaned_models[model_name] = cleaned_model_params
                                cleaned_params[tumor_type] = cleaned_models
                        return cleaned_params
            except Exception as e:
                print(f"Warning: Could not load TCP parameters from {config_path}: {e}")
                print("Using default parameters.")
        
        # Return default parameters
        return default_params
    
    def convert_to_eqd2(self, dose, alpha_beta_ratio, dose_per_fraction, n_fractions=None):
        """
        Convert physical dose to EQD2 (Equivalent Dose in 2 Gy fractions).
        
        Parameters
        ----------
        dose : float
            Physical dose in Gy
        alpha_beta_ratio : float
            Alpha/beta ratio for the tissue
        dose_per_fraction : float
            Dose per fraction in Gy
        n_fractions : int, optional
            Number of fractions (if not provided, calculated from dose/dose_per_fraction)
            
        Returns
        -------
        float
            EQD2 in Gy
        """
        # Delegate to core function
        return convert_to_eqd2(dose, alpha_beta_ratio, dose_per_fraction, n_fractions)
    
    def tcp_poisson(self, dvh, D50, gamma50, alpha_beta=10, dose_per_fraction=2.0):
        """
        Poisson TCP model (Webb & Nahum, 1993).
        
        Based on Poisson statistics for cell survival and tumor control.
        TCP = exp(-N0 * exp(-alpha*D - beta*D^2))
        where N0 is initial clonogen number, D is dose.
        
        Parameters
        ----------
        dvh : pd.DataFrame
            Differential DVH with columns 'dose_gy' and 'volume_cm3'
        D50 : float
            Dose for 50% TCP (Gy)
        gamma50 : float
            Normalized dose-response gradient at D50
        alpha_beta : float, default=10
            Alpha/beta ratio (Gy)
        dose_per_fraction : float, default=2.0
            Dose per fraction (Gy)
            
        Returns
        -------
        float
            TCP value (0-1)
            
        References
        ----------
        Webb S, Nahum AE. A model for calculating tumour control probability
        probability including the effects of inhomogeneous distributions of
        dose and clonogenic cell density. Phys Med Biol. 1993;38(6):653-666.
        """
        try:
            return calculate_tcp_poisson(dvh, D50, gamma50, alpha_beta, dose_per_fraction)
        except ValueError:
            return 0.0
    
    def tcp_lkb(self, dose_metrics, TD50, m, n, alpha_beta=10, dose_per_fraction=2.0):
        """
        LKB-adapted TCP model (Okunieff et al., 1995).
        
        Adaptation of Lyman-Kutcher-Burman model for tumor control.
        Uses effective volume concept similar to NTCP but for TCP.
        
        Parameters
        ----------
        dose_metrics : dict
            Dictionary containing dose metrics:
            - 'v_effective': effective volume (cm3)
            - 'max_dose': maximum dose (Gy)
            - 'mean_dose': mean dose (Gy), optional
        TD50 : float
            Dose for 50% TCP at reference volume (Gy)
        m : float
            Slope parameter (dimensionless)
        n : float
            Volume effect parameter (dimensionless)
        alpha_beta : float, default=10
            Alpha/beta ratio (Gy)
        dose_per_fraction : float, default=2.0
            Dose per fraction (Gy)
            
        Returns
        -------
        float
            TCP value (0-1)
            
        References
        ----------
        Okunieff P, Morgan D, Niemierko A, Suit HD. Radiation dose-response
        of human tumors. Int J Radiat Oncol Biol Phys. 1995;32(4):1227-1237.
        """
        try:
            return calculate_tcp_lkb(dose_metrics, TD50, m, n, alpha_beta, dose_per_fraction)
        except ValueError:
            return 0.0
    
    def tcp_logistic(self, dose_metrics, D50, k, alpha_beta=10, dose_per_fraction=2.0):
        """
        Logistic TCP model (Brahme, 1984).
        
        Simple logistic function for dose-response relationship.
        TCP = 1 / (1 + (D50/D)^k)
        
        Parameters
        ----------
        dose_metrics : dict
            Dictionary containing dose metrics:
            - 'mean_dose': mean dose (Gy) or 'max_dose': maximum dose (Gy)
        D50 : float
            Dose for 50% TCP (Gy)
        k : float
            Steepness parameter (dimensionless)
        alpha_beta : float, default=10
            Alpha/beta ratio (Gy)
        dose_per_fraction : float, default=2.0
            Dose per fraction (Gy)
            
        Returns
        -------
        float
            TCP value (0-1)
            
        References
        ----------
        Brahme A. Dosimetric precision requirements in radiation therapy.
        Acta Radiol Oncol. 1984;23(5):379-391.
        """
        try:
            return calculate_tcp_logistic(dose_metrics, D50, k, alpha_beta, dose_per_fraction)
        except ValueError:
            return 0.0
    
    def tcp_eud(self, dvh, D50, gamma50, a=-10, alpha_beta=10, dose_per_fraction=2.0):
        """
        EUD-based TCP model (Niemierko, 1997).
        
        Uses Equivalent Uniform Dose (EUD) concept for TCP calculation.
        TCP = 1 / (1 + (D50/EUD)^(4*gamma50))
        
        Parameters
        ----------
        dvh : pd.DataFrame
            Differential DVH with columns 'dose_gy' and 'volume_cm3'
        D50 : float
            Dose for 50% TCP (Gy)
        gamma50 : float
            Normalized dose-response gradient at D50
        a : float, default=-10
            EUD parameter (negative for tumors, positive for OARs)
        alpha_beta : float, default=10
            Alpha/beta ratio (Gy)
        dose_per_fraction : float, default=2.0
            Dose per fraction (Gy)
            
        Returns
        -------
        float
            TCP value (0-1)
            
        References
        ----------
        Niemierko A. Reporting and analyzing dose distributions: a concept
        of equivalent uniform dose. Med Phys. 1997;24(1):103-110.
        """
        try:
            return calculate_tcp_eud(dvh, D50, gamma50, a, alpha_beta, dose_per_fraction)
        except ValueError:
            return 0.0
    
    def calculate_all_tcp_models(self, dvh, dose_metrics, tumor_type, dose_per_fraction=2.0):
        """
        Calculate TCP using all four models for given tumor type.
        
        Parameters
        ----------
        dvh : pd.DataFrame
            Differential DVH with columns 'dose_gy' and 'volume_cm3'
        dose_metrics : dict
            Dictionary containing dose metrics (mean_dose, max_dose, v_effective, etc.)
        tumor_type : str
            Tumor type (e.g., 'HNSCC', 'Prostate', 'Lung')
        dose_per_fraction : float, default=2.0
            Dose per fraction (Gy)
            
        Returns
        -------
        dict
            Dictionary with TCP values for each model:
            {
                'Poisson_TCP': {'TCP': float, 'parameters_used': dict},
                'LKB_TCP': {'TCP': float, 'parameters_used': dict},
                'Logistic_TCP': {'TCP': float, 'parameters_used': dict},
                'EUD_TCP': {'TCP': float, 'EUD': float, 'parameters_used': dict}
            }
        """
        if tumor_type not in self.literature_params:
            print(f"Warning: No parameters available for tumor type '{tumor_type}'")
            return {}
        
        tumor_params = self.literature_params[tumor_type]
        results = {}
        
        # 1. Poisson TCP Model
        try:
            params = tumor_params['Poisson_TCP']
            tcp_poisson = self.tcp_poisson(
                dvh, 
                params['D50'], 
                params['gamma50'],
                params['alpha_beta'],
                dose_per_fraction
            )
            results['Poisson_TCP'] = {
                'TCP': tcp_poisson,
                'parameters_used': params
            }
        except Exception as e:
            print(f"Error calculating Poisson TCP for {tumor_type}: {e}")
            results['Poisson_TCP'] = {'TCP': 0.0, 'error': str(e)}
        
        # 2. LKB-adapted TCP Model
        try:
            params = tumor_params['LKB_TCP']
            dose_metrics_copy = dose_metrics.copy()
            if 'v_effective' not in dose_metrics_copy:
                # Calculate v_effective if not provided
                if dvh is not None and len(dvh) > 0:
                    total_vol = dvh['volume_cm3'].sum()
                    dose_metrics_copy['v_effective'] = total_vol
                else:
                    dose_metrics_copy['v_effective'] = 1.0
            
            tcp_lkb = self.tcp_lkb(
                dose_metrics_copy,
                params['TD50'],
                params['m'],
                params['n'],
                params['alpha_beta'],
                dose_per_fraction
            )
            results['LKB_TCP'] = {
                'TCP': tcp_lkb,
                'parameters_used': params
            }
        except Exception as e:
            print(f"Error calculating LKB TCP for {tumor_type}: {e}")
            results['LKB_TCP'] = {'TCP': 0.0, 'error': str(e)}
        
        # 3. Logistic TCP Model
        try:
            params = tumor_params['Logistic_TCP']
            tcp_logistic = self.tcp_logistic(
                dose_metrics,
                params['D50'],
                params['k'],
                params['alpha_beta'],
                dose_per_fraction
            )
            results['Logistic_TCP'] = {
                'TCP': tcp_logistic,
                'parameters_used': params
            }
        except Exception as e:
            print(f"Error calculating Logistic TCP for {tumor_type}: {e}")
            results['Logistic_TCP'] = {'TCP': 0.0, 'error': str(e)}
        
        # 4. EUD-based TCP Model
        try:
            params = tumor_params['EUD_TCP']
            tcp_eud = self.tcp_eud(
                dvh,
                params['D50'],
                params['gamma50'],
                params['a'],
                params['alpha_beta'],
                dose_per_fraction
            )
            results['EUD_TCP'] = {
                'TCP': tcp_eud,
                'parameters_used': params
            }
        except Exception as e:
            print(f"Error calculating EUD TCP for {tumor_type}: {e}")
            results['EUD_TCP'] = {'TCP': 0.0, 'error': str(e)}
        
        return results
