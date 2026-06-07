"""
ML Safety and Governance Module
================================

Implements Cohort Consistency Score (CCS) for safe ML extrapolation prevention.

Key Innovation:
Prevents ML predictions on patients who are out-of-distribution (OOD)
from the training cohort, avoiding unsafe extrapolation.

Mathematical Formulation:
-------------------------
CCS = exp(-0.5 · (X - μ)ᵀ Σ⁻¹ (X - μ))

where:
    X = patient feature vector
    μ = training cohort mean
    Σ = training cohort covariance

Interpretation:
    CCS ≈ 1.0 → patient within training cohort
    CCS < 0.1 → patient is out-of-distribution (OOD)
    
Safety Gate:
    If CCS < threshold → disable ML, use traditional models only

Author: KB (rbGyanX Project)
License: MIT
"""

import numpy as np
import pandas as pd
import warnings
from pathlib import Path
import json


class CohortConsistencyChecker:
    """
    Cohort Consistency Score (CCS) - ML Safety Gate
    
    Prevents unsafe ML extrapolation by detecting when a new patient
    is out-of-distribution relative to the training cohort.
    
    This is a critical governance mechanism that rbGyanX uses to
    avoid the common pitfall of ML models: overconfident predictions
    on patients who differ significantly from training data.
    
    Examples
    --------
    >>> # During training (Advanced mode)
    >>> checker = CohortConsistencyChecker()
    >>> checker.fit(training_features)
    >>> checker.save('cohort_stats.json')
    
    >>> # During prediction (Basic mode)
    >>> checker = CohortConsistencyChecker.load('cohort_stats.json')
    >>> is_safe = checker.is_safe_for_ml(new_patient_features)
    >>> if not is_safe:
    >>>     print("⚠️ Patient is OOD - using traditional models only")
    
    References
    ----------
    Mahalanobis distance: Mahalanobis PC (1936). Proc Natl Inst Sci India
    Distribution shift: Recht et al. (2019). NeurIPS
    """
    
    def __init__(self, threshold=0.1, n_features_expected=None):
        """
        Initialize CCS checker
        
        Parameters
        ----------
        threshold : float, optional
            CCS threshold below which patient is considered OOD
            Default: 0.1 (conservative)
        n_features_expected : int, optional
            Expected number of features (for validation)
        """
        self.threshold = threshold
        self.n_features_expected = n_features_expected
        
        # Training cohort statistics (set during fit())
        self.mu = None  # Mean feature vector
        self.sigma = None  # Covariance matrix
        self.sigma_inv = None  # Inverse covariance
        
        # Metadata
        self.n_samples_trained = None
        self.feature_names = None
        self.is_fitted = False
    
    def fit(self, training_features, feature_names=None):
        """
        Fit CCS checker to training cohort
        
        Parameters
        ----------
        training_features : array-like, shape (n_samples, n_features)
            Training cohort feature matrix
        feature_names : list of str, optional
            Names of features
        
        Returns
        -------
        self : CohortConsistencyChecker
            Fitted checker
        """
        # Convert to numpy array
        X = np.array(training_features)
        
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        
        self.n_samples_trained = X.shape[0]
        n_features = X.shape[1]
        
        # Store feature names
        if feature_names is not None:
            self.feature_names = list(feature_names)
            assert len(self.feature_names) == n_features, \
                "Number of feature names must match number of features"
        else:
            self.feature_names = [f"Feature_{i}" for i in range(n_features)]
        
        # Calculate cohort statistics
        self.mu = np.mean(X, axis=0)
        self.sigma = np.cov(X, rowvar=False)
        
        # Handle single feature case
        if n_features == 1:
            self.sigma = np.array([[self.sigma]])
        
        # Add regularization to prevent singular matrix
        # This is critical for small cohorts
        epsilon = 1e-6
        self.sigma += epsilon * np.eye(n_features)
        
        # Compute inverse covariance
        try:
            self.sigma_inv = np.linalg.inv(self.sigma)
        except np.linalg.LinAlgError:
            warnings.warn(
                "Covariance matrix is singular. Using pseudoinverse. "
                "CCS may be unreliable with current training data."
            )
            self.sigma_inv = np.linalg.pinv(self.sigma)
        
        self.is_fitted = True
        self.n_features_expected = n_features
        
        return self
    
    def calculate_ccs(self, patient_features):
        """
        Calculate Cohort Consistency Score for a patient
        
        CCS = exp(-0.5 * mahalanobis_distance²)
        
        Parameters
        ----------
        patient_features : array-like, shape (n_features,)
            Patient feature vector
        
        Returns
        -------
        ccs : float in [0, 1]
            1.0 = perfectly consistent with cohort
            0.0 = completely inconsistent
        
        Raises
        ------
        ValueError
            If checker not fitted or feature dimension mismatch
        """
        if not self.is_fitted:
            raise ValueError(
                "CCS checker not fitted. Call fit() first or load from file."
            )
        
        # Convert to numpy array
        X = np.array(patient_features).flatten()
        
        # Validate feature dimension
        if len(X) != len(self.mu):
            raise ValueError(
                f"Feature dimension mismatch. Expected {len(self.mu)}, "
                f"got {len(X)}"
            )
        
        # Calculate deviation from cohort mean
        diff = X - self.mu
        
        # Calculate Mahalanobis distance
        # D² = (X - μ)ᵀ Σ⁻¹ (X - μ)
        mahal_dist_sq = diff.T @ self.sigma_inv @ diff
        
        # Convert to CCS
        # CCS = exp(-0.5 * D²)
        ccs = np.exp(-0.5 * mahal_dist_sq)
        
        return float(ccs)
    
    def is_safe_for_ml(self, patient_features, threshold=None, verbose=True):
        """
        Safety gate: Check if ML predictions are safe for this patient
        
        Parameters
        ----------
        patient_features : array-like
            Patient feature vector
        threshold : float, optional
            CCS threshold (uses default if not provided)
        verbose : bool, optional
            Print warning if patient is OOD
        
        Returns
        -------
        is_safe : bool
            True if patient is within distribution (ML safe)
            False if patient is OOD (ML unsafe - use traditional models)
        """
        if threshold is None:
            threshold = self.threshold
        
        # Calculate CCS
        ccs = self.calculate_ccs(patient_features)
        
        # Check against threshold
        is_safe = ccs >= threshold
        
        # Warn if unsafe
        if not is_safe and verbose:
            warnings.warn(
                f"\n{'='*70}\n"
                f"⚠️  PATIENT IS OUT-OF-DISTRIBUTION\n"
                f"{'='*70}\n"
                f"Cohort Consistency Score: {ccs:.4f} (threshold: {threshold:.4f})\n"
                f"\n"
                f"This patient differs significantly from the training cohort.\n"
                f"ML predictions may be UNRELIABLE and should NOT be used.\n"
                f"\n"
                f"Action: rbGyanX will disable ML and use traditional models only.\n"
                f"{'='*70}\n",
                stacklevel=2
            )
        
        return is_safe
    
    def get_feature_contributions(self, patient_features):
        """
        Identify which features contribute most to OOD status
        
        Useful for understanding WHY a patient is out-of-distribution
        
        Parameters
        ----------
        patient_features : array-like
            Patient feature vector
        
        Returns
        -------
        contributions : DataFrame
            Feature-wise contributions to Mahalanobis distance
        """
        X = np.array(patient_features).flatten()
        diff = X - self.mu
        
        # Calculate per-feature standardized deviation
        # Using diagonal of Sigma for univariate variance
        std_devs = np.sqrt(np.diag(self.sigma))
        z_scores = diff / std_devs
        
        # Create report
        contributions = pd.DataFrame({
            'Feature': self.feature_names,
            'Patient_Value': X,
            'Cohort_Mean': self.mu,
            'Cohort_Std': std_devs,
            'Deviation': diff,
            'Z_Score': z_scores,
            'Unusual': np.abs(z_scores) > 2  # Flag extreme values
        })
        
        # Sort by absolute z-score
        contributions = contributions.sort_values(
            'Z_Score', 
            key=lambda x: np.abs(x), 
            ascending=False
        )
        
        return contributions
    
    def save(self, filepath):
        """
        Save CCS checker to file for deployment
        
        Parameters
        ----------
        filepath : str or Path
            Output file path (JSON format)
        """
        if not self.is_fitted:
            raise ValueError("Cannot save unfitted CCS checker")
        
        filepath = Path(filepath)
        
        # Prepare data for JSON serialization
        save_data = {
            'threshold': self.threshold,
            'n_features': len(self.mu),
            'n_samples_trained': self.n_samples_trained,
            'feature_names': self.feature_names,
            'mu': self.mu.tolist(),
            'sigma': self.sigma.tolist(),
            'sigma_inv': self.sigma_inv.tolist(),
            'metadata': {
                'version': '1.0',
                'created_by': 'rbGyanX CCS',
                'n_samples': self.n_samples_trained
            }
        }
        
        # Save to JSON
        with open(filepath, 'w') as f:
            json.dump(save_data, f, indent=2)
        
        print(f"[OK] CCS checker saved: {filepath}")
    
    @classmethod
    def load(cls, filepath):
        """
        Load CCS checker from file
        
        Parameters
        ----------
        filepath : str or Path
            Input file path (JSON format)
        
        Returns
        -------
        checker : CohortConsistencyChecker
            Loaded and fitted checker
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"CCS file not found: {filepath}")
        
        # Load from JSON
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Create checker
        checker = cls(
            threshold=data['threshold'],
            n_features_expected=data['n_features']
        )
        
        # Restore state
        checker.mu = np.array(data['mu'])
        checker.sigma = np.array(data['sigma'])
        checker.sigma_inv = np.array(data['sigma_inv'])
        checker.feature_names = data['feature_names']
        checker.n_samples_trained = data['n_samples_trained']
        checker.is_fitted = True
        
        print(f"[OK] CCS checker loaded: {filepath}")
        print(f"     Training cohort: {checker.n_samples_trained} patients")
        print(f"     Features: {len(checker.feature_names)}")
        
        return checker


def create_ccs_report(checker, patient_features, patient_id='Unknown'):
    """
    Generate comprehensive CCS safety report
    
    Parameters
    ----------
    checker : CohortConsistencyChecker
        Fitted CCS checker
    patient_features : array-like
        Patient feature vector
    patient_id : str, optional
        Patient identifier
    
    Returns
    -------
    report : dict
        Comprehensive safety assessment
    """
    # Calculate CCS
    ccs = checker.calculate_ccs(patient_features)
    is_safe = checker.is_safe_for_ml(patient_features, verbose=False)
    
    # Get feature contributions
    contributions = checker.get_feature_contributions(patient_features)
    
    # Identify unusual features (|z| > 2)
    unusual_features = contributions[contributions['Unusual']].copy()
    
    # Create report
    report = {
        'patient_id': patient_id,
        'ccs_score': ccs,
        'is_safe_for_ml': is_safe,
        'threshold': checker.threshold,
        'n_unusual_features': len(unusual_features),
        'unusual_features': unusual_features.to_dict('records'),
        'all_feature_contributions': contributions.to_dict('records'),
        'recommendation': (
            'ML predictions allowed' if is_safe else 
            'ML predictions DISABLED - use traditional models'
        )
    }
    
    return report


# Example usage
if __name__ == '__main__':
    # Simulate training cohort (100 patients, 5 features)
    np.random.seed(42)
    
    training_cohort = np.random.multivariate_normal(
        mean=[50, 60, 2.0, 100, 70],  # Age, Dmean, Stage, Volume, Total_dose
        cov=np.diag([100, 25, 0.5, 400, 25]),
        size=100
    )
    
    feature_names = ['Age', 'GTV_Mean_Dose', 'Stage', 'GTV_Volume_cc', 'Total_Dose']
    
    # Fit CCS checker
    checker = CohortConsistencyChecker(threshold=0.1)
    checker.fit(training_cohort, feature_names=feature_names)
    
    # Save for deployment
    checker.save('institutional_ccs.json')
    
    # Test with in-distribution patient
    patient_in = [52, 62, 2.1, 105, 72]
    ccs_in = checker.calculate_ccs(patient_in)
    safe_in = checker.is_safe_for_ml(patient_in)
    print(f"\nIn-distribution patient: CCS = {ccs_in:.4f}, Safe = {safe_in}")
    
    # Test with out-of-distribution patient
    patient_out = [25, 80, 4.0, 300, 50]  # Very different!
    ccs_out = checker.calculate_ccs(patient_out)
    safe_out = checker.is_safe_for_ml(patient_out)
    print(f"Out-of-distribution patient: CCS = {ccs_out:.4f}, Safe = {safe_out}")
    
    # Generate detailed report
    report = create_ccs_report(checker, patient_out, patient_id='Test_001')
    print("\nDetailed Report:")
    print(f"  CCS: {report['ccs_score']:.4f}")
    print(f"  Safe: {report['is_safe_for_ml']}")
    print(f"  Unusual features: {report['n_unusual_features']}")
    print(f"  Recommendation: {report['recommendation']}")

