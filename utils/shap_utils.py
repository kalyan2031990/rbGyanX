#!/usr/bin/env python3
"""
SHAP Utilities for TCP_NTCP Pipeline v2.0
==========================================

Reusable SHAP explainability functions for ML models.

These functions are extracted from shap_suppl.py to enable integration
into the main analysis pipeline (code3, code6) while maintaining 
backward compatibility with the standalone SHAP script.

Author: TCP_NTCP Pipeline Team
Version: 2.0.0
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import shap
from typing import Tuple, Union, List
from pathlib import Path


def safe_shap_values(model, X_train, X_test):
    """
    Generate SHAP values with automatic explainer selection.
    
    Tries TreeExplainer first (for XGBoost), falls back to KernelExplainer (for ANN).
    
    Parameters
    ----------
    model : sklearn estimator or xgboost model
        Trained ML model
    X_train : pd.DataFrame
        Training features for KernelExplainer background
    X_test : pd.DataFrame
        Test features to explain
        
    Returns
    -------
    explainer : shap.Explainer
        SHAP explainer object
    shap_values : np.ndarray
        SHAP values for X_test
        
    Examples
    --------
    >>> explainer, shap_values = safe_shap_values(xgb_model, X_train, X_test)
    """
    # try a TreeExplainer first (works for XGBoost)
    try:
        explainer = shap.TreeExplainer(model)
        try:
            sv = explainer.shap_values(X_test, check_additivity=False)
        except TypeError:
            sv = explainer.shap_values(X_test)
        return explainer, sv
    except Exception:
        pass
    # fallback: KernelExplainer (works for ANN)
    f = (lambda Z: model.predict_proba(Z)[:,1]) if hasattr(model, "predict_proba") else (lambda Z: model.predict(Z))
    try:
        background = shap.sample(X_train, min(50, max(1, X_train.shape[0])))
    except Exception:
        background = X_train.iloc[:min(50, len(X_train)), :]
    explainer = shap.KernelExplainer(f, background, link="logit")
    try:
        sv = explainer.shap_values(X_test, nsamples=100)
    except Exception:
        sv = explainer.shap_values(X_test)
    return explainer, sv


def to_matrix(shap_values):
    """
    Convert SHAP values to matrix format.
    
    Handles binary classification where SHAP returns list of 2 arrays.
    
    Parameters
    ----------
    shap_values : list or np.ndarray
        SHAP values from explainer
        
    Returns
    -------
    np.ndarray
        SHAP values as matrix
    """
    # shap may return list for multiclass; here binary -> 2 classes sometimes
    if isinstance(shap_values, list) and len(shap_values)==2:
        # choose positive class
        return np.array(shap_values[1])
    return np.array(shap_values)


def plot_summary_bar(shap_values, X, output_path, dpi=1200):
    """
    Create SHAP summary bar plot (global feature importance).
    
    Parameters
    ----------
    shap_values : np.ndarray
        SHAP values matrix
    X : pd.DataFrame
        Feature dataframe
    output_path : str or Path
        Output file path (PNG)
    dpi : int, default=1200
        Resolution for publication quality
        
    Examples
    --------
    >>> plot_summary_bar(shap_values, X_test, "shap_bar.png")
    """
    plt.figure(figsize=(6,5))
    shap.summary_plot(shap_values, X, plot_type="bar", show=False)
    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close()


def plot_beeswarm(shap_values, X, output_path, dpi=1200):
    """
    Create SHAP beeswarm plot (feature directionality).
    
    Shows how feature values affect predictions (red=high value, blue=low value).
    
    Parameters
    ----------
    shap_values : np.ndarray
        SHAP values matrix
    X : pd.DataFrame
        Feature dataframe
    output_path : str or Path
        Output file path (PNG)
    dpi : int, default=1200
        Resolution for publication quality
    """
    plt.figure(figsize=(7,5))
    shap.summary_plot(shap_values, X, show=False)
    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close()


def generate_shap_caption(shap_values, feature_names, model_name, organ_name):
    """
    Generate caption with top 3 features by mean |SHAP|.
    
    Parameters
    ----------
    shap_values : np.ndarray
        SHAP values matrix
    feature_names : list or pd.Index
        Feature names
    model_name : str
        Model name (e.g., "XGBoost", "ANN")
    organ_name : str
        Organ/structure name (e.g., "Parotid")
        
    Returns
    -------
    str
        Caption text with top features
        
    Examples
    --------
    >>> caption = generate_shap_caption(shap_values, X.columns, "XGBoost", "Parotid")
    """
    M = np.mean(np.abs(shap_values), axis=0)
    order = np.argsort(M)[::-1]
    top = [(feature_names[i], float(M[i])) for i in order[:3]]
    parts = [f"Supplementary SHAP for {organ_name} – {model_name}: top features by mean |SHAP|"]
    for k,(n,v) in enumerate(top,1):
        parts.append(f"{k}) {n} (mean|SHAP|={v:.3g})")
    parts.append("Bars show global importance; beeswarm shows directionality (red=higher feature values).")
    return "; ".join(parts)

