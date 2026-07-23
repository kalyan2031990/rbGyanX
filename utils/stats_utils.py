"""
Statistical analysis utilities
"""
from scipy import stats
import numpy as np
from typing import Tuple, List


def calculate_confidence_interval(data: np.ndarray, confidence: float = 0.95) -> Tuple[float, float, float]:
    """
    Calculate confidence interval for data
    
    Parameters
    ----------
    data : np.ndarray
        Data array
    confidence : float
        Confidence level (default: 0.95)
    
    Returns
    -------
    tuple
        (mean, lower_bound, upper_bound)
    """
    n = len(data)
    if n < 2:
        return float(np.mean(data)), float(np.mean(data)), float(np.mean(data))
    
    mean = np.mean(data)
    se = stats.sem(data)
    ci = se * stats.t.ppf((1 + confidence) / 2., n-1)
    
    return float(mean), float(mean - ci), float(mean + ci)


def bootstrap_ci(data: np.ndarray, 
                 n_bootstrap: int = 1000, 
                 confidence: float = 0.95) -> Tuple[float, float, float]:
    """
    Bootstrap confidence interval
    
    Parameters
    ----------
    data : np.ndarray
        Data array
    n_bootstrap : int
        Number of bootstrap samples
    confidence : float
        Confidence level (default: 0.95)
    
    Returns
    -------
    tuple
        (mean, lower_bound, upper_bound)
    """
    if len(data) < 2:
        return float(np.mean(data)), float(np.mean(data)), float(np.mean(data))
    
    bootstraps = []
    for _ in range(n_bootstrap):
        sample = np.random.choice(data, len(data), replace=True)
        bootstraps.append(np.mean(sample))
    
    lower = np.percentile(bootstraps, (1 - confidence) / 2 * 100)
    upper = np.percentile(bootstraps, (1 + confidence) / 2 * 100)
    
    return float(np.mean(data)), float(lower), float(upper)


def calculate_correlation(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """
    Calculate Pearson correlation coefficient and p-value
    
    Parameters
    ----------
    x : np.ndarray
        First variable
    y : np.ndarray
        Second variable
    
    Returns
    -------
    tuple
        (correlation_coefficient, p_value)
    """
    if len(x) != len(y) or len(x) < 2:
        return 0.0, 1.0
    
    corr, p_value = stats.pearsonr(x, y)
    return float(corr), float(p_value)


def calculate_mann_whitney_u(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """
    Calculate Mann-Whitney U test statistic and p-value
    
    Parameters
    ----------
    x : np.ndarray
        First group
    y : np.ndarray
        Second group
    
    Returns
    -------
    tuple
        (U_statistic, p_value)
    """
    if len(x) < 1 or len(y) < 1:
        return 0.0, 1.0
    
    u_stat, p_value = stats.mannwhitneyu(x, y, alternative='two-sided')
    return float(u_stat), float(p_value)

