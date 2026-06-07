"""
Uncertainty-Aware Radiobiological Models
=========================================

Implements uncertainty propagation for TCP/NTCP predictions.

Key Innovation:
Instead of reporting TCP = 0.78 (false precision),
report TCP = 0.78 ± 0.11 (honest uncertainty)

Methods:
1. Monte Carlo parameter sampling
2. First-order error propagation
3. Confidence interval estimation

Author: KB (rbGyanX Project)
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import erf


class UncertaintyAwareTCP:
    """
    Uncertainty-Aware Tumor Control Probability
    
    Propagates parameter uncertainty through TCP models to provide
    confidence bounds on predictions.
    
    Mathematical Formulation:
    -------------------------
    TCP = f(DVH, θ) where θ = (α, ρ, Tk, σ)
    
    Uncertainty propagation via Monte Carlo:
        σ_TCP² = Var[f(DVH, θ̃)]
    
    where θ̃ ~ N(θ, Σ_θ)
    
    Output:
        uTCP = E[TCP] ± σ_TCP
    
    Interpretation:
        - Narrow uncertainty → robust prediction
        - Wide uncertainty → model extrapolation risk
    
    Examples
    --------
    >>> utcp = UncertaintyAwareTCP()
    >>> tcp_mean, tcp_std = utcp.calculate_poisson_utcp(
    ...     dvh=tumor_dvh,
    ...     parameters={'alpha': 0.30, 'rho': 1e7, 'Tk': 30},
    ...     uncertainties={'alpha': 0.05, 'rho': 2e6, 'Tk': 5}
    ... )
    >>> print(f"TCP = {tcp_mean:.2f} ± {tcp_std:.2f}")
    TCP = 0.78 ± 0.11
    
    References
    ----------
    Taylor JR (1997). An Introduction to Error Analysis. 2nd Ed.
    """
    
    def __init__(self, n_samples=1000, confidence_level=0.95, random_seed=42):
        """
        Initialize uncertainty-aware TCP calculator
        
        Parameters
        ----------
        n_samples : int
            Number of Monte Carlo samples (default: 1000)
        confidence_level : float
            Confidence level for intervals (default: 0.95)
        random_seed : int
            Random seed for reproducibility
        """
        self.n_samples = n_samples
        self.confidence_level = confidence_level
        self.random_seed = random_seed
        np.random.seed(random_seed)
    
    def calculate_poisson_utcp(self, dvh, parameters, uncertainties):
        """
        Calculate uncertainty-aware Poisson TCP
        
        TCP_Poisson = exp(-ρ · V_tumor · e^(-α·D_eff))
        
        Parameters
        ----------
        dvh : DataFrame
            Tumor DVH with 'Dose[Gy]' and 'Volume[%]'
        parameters : dict
            {'alpha': float, 'rho': float, 'Tk': float}
            Mean parameter values
        uncertainties : dict
            {'alpha': float, 'rho': float, 'Tk': float}
            Parameter standard deviations
        
        Returns
        -------
        tcp_mean : float
            Expected TCP value
        tcp_std : float
            TCP standard deviation
        tcp_ci : tuple
            (lower, upper) confidence interval
        """
        tcp_samples = []
        
        # Monte Carlo sampling
        for _ in range(self.n_samples):
            # Sample parameters from normal distributions
            alpha_sample = np.random.normal(
                parameters['alpha'], 
                uncertainties.get('alpha', 0)
            )
            rho_sample = np.random.normal(
                parameters['rho'],
                uncertainties.get('rho', 0)
            )
            Tk_sample = np.random.normal(
                parameters['Tk'],
                uncertainties.get('Tk', 0)
            )
            
            # Ensure positive parameters
            alpha_sample = max(alpha_sample, 0.01)
            rho_sample = max(rho_sample, 1e5)
            Tk_sample = max(Tk_sample, 1)
            
            # Calculate TCP with sampled parameters
            tcp = self._poisson_tcp_single(
                dvh, 
                alpha=alpha_sample,
                rho=rho_sample,
                Tk=Tk_sample
            )
            
            tcp_samples.append(tcp)
        
        # Calculate statistics
        tcp_samples = np.array(tcp_samples)
        tcp_mean = np.mean(tcp_samples)
        tcp_std = np.std(tcp_samples)
        
        # Confidence interval
        alpha_ci = 1 - self.confidence_level
        tcp_ci = (
            np.percentile(tcp_samples, 100 * alpha_ci / 2),
            np.percentile(tcp_samples, 100 * (1 - alpha_ci / 2))
        )
        
        return tcp_mean, tcp_std, tcp_ci
    
    def _poisson_tcp_single(self, dvh, alpha, rho, Tk):
        """
        Single Poisson TCP calculation
        
        Simplified implementation - replace with your actual TCP function
        """
        # Find dose and volume columns
        dose_col = None
        vol_col = None
        
        for col in dvh.columns:
            if 'dose' in col.lower() and 'gy' in col.lower():
                dose_col = col
            if 'volume' in col.lower() and '%' in col.lower():
                vol_col = col
        
        if dose_col is None:
            if 'Dose[Gy]' in dvh.columns:
                dose_col = 'Dose[Gy]'
            elif 'dose_gy' in dvh.columns:
                dose_col = 'dose_gy'
            else:
                # Use first numeric column as dose
                dose_col = dvh.select_dtypes(include=[np.number]).columns[0]
        
        if vol_col is None:
            if 'Volume[%]' in dvh.columns:
                vol_col = 'Volume[%]'
            elif 'volume_percent' in dvh.columns:
                vol_col = 'volume_percent'
            else:
                # Use second numeric column as volume
                numeric_cols = dvh.select_dtypes(include=[np.number]).columns
                vol_col = numeric_cols[1] if len(numeric_cols) > 1 else numeric_cols[0]
        
        # Calculate effective dose (weighted average)
        doses = dvh[dose_col].values
        volumes = dvh[vol_col].values / 100.0  # Convert to fraction
        
        # Mean dose (weighted)
        mean_dose = np.average(doses, weights=volumes)
        
        # Tumor volume (assuming total = 100 cc, or calculate from volumes)
        # For simplicity, use a standard volume
        V_tumor = 100  # cc
        
        # Poisson TCP
        # TCP = exp(-ρ · V · exp(-α · D))
        tcp = np.exp(-rho * V_tumor * np.exp(-alpha * mean_dose))
        
        return min(max(tcp, 0.0), 1.0)  # Clip to [0, 1]
    
    def calculate_lkb_utcp(self, dvh, parameters, uncertainties):
        """
        Calculate uncertainty-aware LKB TCP
        
        Parameters
        ----------
        dvh : DataFrame
            Tumor DVH
        parameters : dict
            {'TD50': float, 'm': float, 'n': float}
        uncertainties : dict
            Parameter uncertainties
        
        Returns
        -------
        tcp_mean, tcp_std, tcp_ci : floats and tuple
        """
        tcp_samples = []
        
        for _ in range(self.n_samples):
            # Sample parameters
            TD50_sample = np.random.normal(
                parameters['TD50'],
                uncertainties.get('TD50', 0)
            )
            m_sample = np.random.normal(
                parameters['m'],
                uncertainties.get('m', 0)
            )
            n_sample = np.random.normal(
                parameters['n'],
                uncertainties.get('n', 0)
            )
            
            # Bounds
            TD50_sample = max(TD50_sample, 10)
            m_sample = max(m_sample, 0.1)
            n_sample = max(min(n_sample, 1.0), 0.01)
            
            # Calculate TCP
            tcp = self._lkb_tcp_single(dvh, TD50_sample, m_sample, n_sample)
            tcp_samples.append(tcp)
        
        tcp_samples = np.array(tcp_samples)
        tcp_mean = np.mean(tcp_samples)
        tcp_std = np.std(tcp_samples)
        
        alpha_ci = 1 - self.confidence_level
        tcp_ci = (
            np.percentile(tcp_samples, 100 * alpha_ci / 2),
            np.percentile(tcp_samples, 100 * (1 - alpha_ci / 2))
        )
        
        return tcp_mean, tcp_std, tcp_ci
    
    def _lkb_tcp_single(self, dvh, TD50, m, n):
        """Single LKB TCP calculation"""
        # Find dose and volume columns
        dose_col = None
        vol_col = None
        
        for col in dvh.columns:
            if 'dose' in col.lower() and 'gy' in col.lower():
                dose_col = col
            if 'volume' in col.lower() and '%' in col.lower():
                vol_col = col
        
        if dose_col is None:
            if 'Dose[Gy]' in dvh.columns:
                dose_col = 'Dose[Gy]'
            elif 'dose_gy' in dvh.columns:
                dose_col = 'dose_gy'
            else:
                dose_col = dvh.select_dtypes(include=[np.number]).columns[0]
        
        if vol_col is None:
            if 'Volume[%]' in dvh.columns:
                vol_col = 'Volume[%]'
            elif 'volume_percent' in dvh.columns:
                vol_col = 'volume_percent'
            else:
                numeric_cols = dvh.select_dtypes(include=[np.number]).columns
                vol_col = numeric_cols[1] if len(numeric_cols) > 1 else numeric_cols[0]
        
        # Calculate gEUD
        doses = dvh[dose_col].values
        volumes = dvh[vol_col].values / 100.0
        
        a = 1 / n  # Volume effect parameter
        gEUD = (np.sum(volumes * doses**a))**(1/a)
        
        # LKB formula
        t = (gEUD - TD50) / (m * TD50)
        tcp = 0.5 * (1 + erf(t / np.sqrt(2)))
        
        return min(max(tcp, 0.0), 1.0)
    
    def generate_uncertainty_report(self, dvh, model_results):
        """
        Generate comprehensive uncertainty report
        
        Parameters
        ----------
        dvh : DataFrame
            Tumor DVH
        model_results : dict
            Results from multiple models with uncertainties
        
        Returns
        -------
        report : DataFrame
            Comprehensive uncertainty analysis
        """
        results = []
        
        for model_name, result in model_results.items():
            results.append({
                'Model': model_name,
                'TCP_mean': result['tcp_mean'],
                'TCP_std': result['tcp_std'],
                'TCP_CI_lower': result['tcp_ci'][0],
                'TCP_CI_upper': result['tcp_ci'][1],
                'Uncertainty_level': self._classify_uncertainty(result['tcp_std'])
            })
        
        return pd.DataFrame(results)
    
    def _classify_uncertainty(self, std):
        """Classify uncertainty level"""
        if std < 0.05:
            return 'Low (Robust)'
        elif std < 0.15:
            return 'Moderate'
        else:
            return 'High (Caution)'


# Integration helper function
def calculate_all_utcp(dvh, clinical_params=None):
    """
    Calculate uTCP for all standard models
    
    Parameters
    ----------
    dvh : DataFrame
        Tumor DVH
    clinical_params : dict, optional
        Patient-specific parameters
    
    Returns
    -------
    results : dict
        uTCP results for all models
    """
    utcp = UncertaintyAwareTCP(n_samples=1000)
    
    # Default parameter uncertainties (from literature)
    poisson_params = {
        'alpha': 0.30,
        'rho': 1e7,
        'Tk': 30
    }
    poisson_uncertainties = {
        'alpha': 0.05,  # ±0.05 Gy^-1
        'rho': 2e6,     # ±2e6 cells/cc
        'Tk': 5         # ±5 days
    }
    
    lkb_params = {
        'TD50': 60,
        'm': 0.3,
        'n': 0.3
    }
    lkb_uncertainties = {
        'TD50': 5,   # ±5 Gy
        'm': 0.05,   # ±0.05
        'n': 0.1     # ±0.1
    }
    
    # Override with clinical params if provided
    if clinical_params:
        poisson_params.update({k: v for k, v in clinical_params.items() if k in poisson_params})
        lkb_params.update({k: v for k, v in clinical_params.items() if k in lkb_params})
    
    # Calculate uTCP for each model
    results = {}
    
    # Poisson uTCP
    try:
        tcp_mean, tcp_std, tcp_ci = utcp.calculate_poisson_utcp(
            dvh, poisson_params, poisson_uncertainties
        )
        results['Poisson'] = {
            'tcp_mean': tcp_mean,
            'tcp_std': tcp_std,
            'tcp_ci': tcp_ci
        }
    except Exception as e:
        print(f"Warning: Could not calculate Poisson uTCP: {e}")
    
    # LKB uTCP
    try:
        tcp_mean, tcp_std, tcp_ci = utcp.calculate_lkb_utcp(
            dvh, lkb_params, lkb_uncertainties
        )
        results['LKB'] = {
            'tcp_mean': tcp_mean,
            'tcp_std': tcp_std,
            'tcp_ci': tcp_ci
        }
    except Exception as e:
        print(f"Warning: Could not calculate LKB uTCP: {e}")
    
    return results


# Example usage
if __name__ == '__main__':
    # Example DVH
    sample_dvh = pd.DataFrame({
        'Dose[Gy]': np.linspace(0, 70, 100),
        'Volume[%]': 100 * np.exp(-np.linspace(0, 70, 100) / 20)
    })
    
    # Calculate uTCP
    results = calculate_all_utcp(sample_dvh)
    
    for model, result in results.items():
        print(f"{model} TCP: {result['tcp_mean']:.3f} ± {result['tcp_std']:.3f}")
        print(f"  95% CI: [{result['tcp_ci'][0]:.3f}, {result['tcp_ci'][1]:.3f}]")

