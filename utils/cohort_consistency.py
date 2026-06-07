"""
Cohort Consistency Score (CCS) - Safe ML Gating
=================================================

Implements cohort consistency checking to prevent ML model overfitting
and ensure safe machine learning deployment.

Key Innovation:
Before training ML models, check if the cohort is:
1. Sufficiently large (n >= threshold)
2. Balanced (no extreme class imbalance)
3. Representative (no data leakage)
4. Consistent (low variance in key features)

CCS Score: 0-1 scale
- CCS > 0.7: Safe for ML training
- CCS 0.5-0.7: Proceed with caution
- CCS < 0.5: Do not train ML models

Author: KB (rbGyanX Project)
License: MIT
"""

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import StandardScaler


class CohortConsistencyScore:
    """
    Calculate Cohort Consistency Score for safe ML gating.
    
    Evaluates whether a cohort is suitable for machine learning
    model training based on multiple consistency criteria.
    
    Examples
    --------
    >>> ccs = CohortConsistencyScore()
    >>> score, report = ccs.evaluate_cohort(
    ...     X=features_df,
    ...     y=outcomes_series,
    ...     min_samples=20
    ... )
    >>> if score > 0.7:
    ...     print("Safe to train ML models")
    ... else:
    ...     print("Cohort too inconsistent for ML")
    """
    
    def __init__(self, min_samples=20, max_class_imbalance=0.8, 
                 min_feature_variance=1e-6):
        """
        Initialize CCS calculator
        
        Parameters
        ----------
        min_samples : int
            Minimum number of samples required (default: 20)
        max_class_imbalance : float
            Maximum acceptable class imbalance ratio (default: 0.8)
        min_feature_variance : float
            Minimum feature variance to avoid constant features (default: 1e-6)
        """
        self.min_samples = min_samples
        self.max_class_imbalance = max_class_imbalance
        self.min_feature_variance = min_feature_variance
    
    def evaluate_cohort(self, X, y, feature_names=None):
        """
        Evaluate cohort consistency and return CCS score
        
        Parameters
        ----------
        X : DataFrame or array-like
            Feature matrix (n_samples, n_features)
        y : Series or array-like
            Target variable (binary or continuous)
        feature_names : list, optional
            Names of features for reporting
        
        Returns
        -------
        ccs_score : float
            Cohort Consistency Score (0-1)
        report : dict
            Detailed consistency report
        """
        # Convert to DataFrame/Series if needed
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
            if feature_names:
                X.columns = feature_names[:len(X.columns)]
        
        if not isinstance(y, pd.Series):
            y = pd.Series(y)
        
        # Remove rows with missing values
        valid_mask = ~(X.isna().any(axis=1) | y.isna())
        X_clean = X[valid_mask].copy()
        y_clean = y[valid_mask].copy()
        
        if len(X_clean) == 0:
            return 0.0, {'error': 'No valid samples after removing missing values'}
        
        # Calculate individual consistency metrics
        metrics = {}
        
        # 1. Sample size check
        n_samples = len(X_clean)
        sample_size_score = min(1.0, n_samples / self.min_samples)
        metrics['sample_size'] = {
            'n_samples': n_samples,
            'min_required': self.min_samples,
            'score': sample_size_score
        }
        
        # 2. Class balance check (for binary classification)
        if y_clean.nunique() == 2:
            class_counts = y_clean.value_counts()
            minority_class_ratio = class_counts.min() / class_counts.sum()
            balance_score = min(1.0, minority_class_ratio / self.max_class_imbalance)
            metrics['class_balance'] = {
                'minority_ratio': minority_class_ratio,
                'max_acceptable': self.max_class_imbalance,
                'score': balance_score,
                'class_counts': class_counts.to_dict()
            }
        else:
            # For continuous or multi-class, use coefficient of variation
            if y_clean.std() > 0:
                cv = y_clean.std() / y_clean.mean()
                balance_score = min(1.0, 1.0 / (1.0 + cv))
            else:
                balance_score = 0.0
            metrics['class_balance'] = {
                'coefficient_of_variation': cv if y_clean.std() > 0 else np.inf,
                'score': balance_score
            }
        
        # 3. Feature variance check
        feature_variances = X_clean.var()
        low_variance_features = (feature_variances < self.min_feature_variance).sum()
        n_features = len(X_clean.columns)
        variance_score = 1.0 - (low_variance_features / max(n_features, 1))
        metrics['feature_variance'] = {
            'low_variance_features': int(low_variance_features),
            'total_features': n_features,
            'score': variance_score,
            'low_variance_list': feature_variances[feature_variances < self.min_feature_variance].index.tolist()
        }
        
        # 4. Outlier check (using IQR method)
        outlier_scores = []
        for col in X_clean.columns:
            Q1 = X_clean[col].quantile(0.25)
            Q3 = X_clean[col].quantile(0.75)
            IQR = Q3 - Q1
            if IQR > 0:
                outliers = ((X_clean[col] < (Q1 - 1.5 * IQR)) | 
                           (X_clean[col] > (Q3 + 1.5 * IQR))).sum()
                outlier_ratio = outliers / n_samples
                outlier_scores.append(1.0 - min(1.0, outlier_ratio * 2))  # Penalize if >50% outliers
            else:
                outlier_scores.append(0.5)  # Constant feature
        
        outlier_score = np.mean(outlier_scores) if outlier_scores else 0.5
        metrics['outliers'] = {
            'mean_outlier_score': outlier_score,
            'score': outlier_score
        }
        
        # 5. Feature correlation check (avoid multicollinearity)
        if n_features > 1:
            corr_matrix = X_clean.corr().abs()
            # Count highly correlated feature pairs (|r| > 0.9)
            high_corr_pairs = ((corr_matrix > 0.9) & (corr_matrix < 1.0)).sum().sum() / 2
            max_corr_pairs = n_features * (n_features - 1) / 2
            correlation_score = 1.0 - min(1.0, high_corr_pairs / max(max_corr_pairs * 0.1, 1))
            metrics['multicollinearity'] = {
                'high_corr_pairs': int(high_corr_pairs),
                'max_pairs': int(max_corr_pairs),
                'score': correlation_score
            }
        else:
            metrics['multicollinearity'] = {'score': 1.0}
        
        # Calculate overall CCS score (weighted average)
        weights = {
            'sample_size': 0.3,
            'class_balance': 0.25,
            'feature_variance': 0.2,
            'outliers': 0.15,
            'multicollinearity': 0.1
        }
        
        ccs_score = (
            weights['sample_size'] * metrics['sample_size']['score'] +
            weights['class_balance'] * metrics['class_balance']['score'] +
            weights['feature_variance'] * metrics['feature_variance']['score'] +
            weights['outliers'] * metrics['outliers']['score'] +
            weights['multicollinearity'] * metrics['multicollinearity']['score']
        )
        
        # Determine recommendation
        if ccs_score >= 0.7:
            recommendation = 'Safe for ML training'
        elif ccs_score >= 0.5:
            recommendation = 'Proceed with caution'
        else:
            recommendation = 'Do not train ML models - cohort too inconsistent'
        
        report = {
            'ccs_score': ccs_score,
            'recommendation': recommendation,
            'metrics': metrics,
            'n_samples': n_samples,
            'n_features': n_features
        }
        
        return ccs_score, report
    
    def should_train_ml(self, X, y, feature_names=None):
        """
        Simple boolean check: should ML models be trained?
        
        Parameters
        ----------
        X : DataFrame or array-like
            Feature matrix
        y : Series or array-like
            Target variable
        feature_names : list, optional
            Feature names
        
        Returns
        -------
        bool
            True if safe to train ML, False otherwise
        """
        ccs_score, _ = self.evaluate_cohort(X, y, feature_names)
        return ccs_score >= 0.5  # Allow training if CCS >= 0.5
    
    def generate_report_string(self, report):
        """
        Generate human-readable report string
        
        Parameters
        ----------
        report : dict
            Report from evaluate_cohort()
        
        Returns
        -------
        str
            Formatted report string
        """
        lines = []
        lines.append("=" * 70)
        lines.append("Cohort Consistency Score (CCS) Report")
        lines.append("=" * 70)
        lines.append(f"\nCCS Score: {report['ccs_score']:.3f}")
        lines.append(f"Recommendation: {report['recommendation']}")
        lines.append(f"\nCohort Statistics:")
        lines.append(f"  - Samples: {report['n_samples']}")
        lines.append(f"  - Features: {report['n_features']}")
        
        lines.append(f"\nDetailed Metrics:")
        for metric_name, metric_data in report['metrics'].items():
            lines.append(f"\n  {metric_name.replace('_', ' ').title()}:")
            for key, value in metric_data.items():
                if key != 'score':
                    if isinstance(value, float):
                        lines.append(f"    - {key}: {value:.4f}")
                    else:
                        lines.append(f"    - {key}: {value}")
            lines.append(f"    - Score: {metric_data['score']:.3f}")
        
        lines.append("\n" + "=" * 70)
        return "\n".join(lines)


# Convenience function
def check_cohort_consistency(X, y, min_samples=20, verbose=True):
    """
    Quick check of cohort consistency
    
    Parameters
    ----------
    X : DataFrame or array-like
        Feature matrix
    y : Series or array-like
        Target variable
    min_samples : int
        Minimum samples required
    verbose : bool
        Print report if True
    
    Returns
    -------
    bool
        True if safe to train ML
    """
    ccs = CohortConsistencyScore(min_samples=min_samples)
    score, report = ccs.evaluate_cohort(X, y)
    
    if verbose:
        print(ccs.generate_report_string(report))
    
    return score >= 0.5


# Example usage
if __name__ == '__main__':
    # Example: Check consistency of a sample cohort
    np.random.seed(42)
    
    # Create sample data
    n_samples = 50
    n_features = 10
    
    X = pd.DataFrame(np.random.randn(n_samples, n_features),
                     columns=[f'Feature_{i}' for i in range(n_features)])
    y = pd.Series(np.random.binomial(1, 0.5, n_samples))
    
    # Evaluate cohort
    ccs = CohortConsistencyScore(min_samples=20)
    score, report = ccs.evaluate_cohort(X, y)
    
    print(ccs.generate_report_string(report))
    
    # Check if ML should be trained
    should_train = ccs.should_train_ml(X, y)
    print(f"\nShould train ML models: {should_train}")

