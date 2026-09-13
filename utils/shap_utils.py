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

from contextlib import contextmanager

import matplotlib
import numpy as np

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import shap


@contextmanager
def _figure_scope():
    """Close every matplotlib figure created inside the block.

    ``plt.close()`` closes only the *current* figure. Both plotting helpers below open a figure
    with ``plt.figure(...)`` and then call ``shap.summary_plot``, which opens one of its own and
    makes it current -- so the bare ``plt.close()`` they used to end with closed shap's figure
    and orphaned theirs. Each call leaked exactly one figure, which over a cohort run (organs x
    models x two plot types) trips matplotlib's 20-figure warning and grows memory for the rest
    of the run.

    Closing by difference rather than with ``plt.close("all")`` keeps any figure the caller had
    open before the call, which matters because these helpers are called from scripts that build
    other figures of their own.
    """
    before = set(plt.get_fignums())
    try:
        yield
    finally:
        for number in set(plt.get_fignums()) - before:
            plt.close(number)


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
    Convert SHAP values to a 2-D (samples x features) matrix.

    Handles both shapes SHAP uses for binary classification:

    * a list of two arrays, one per class (shap < 0.45, and KernelExplainer);
    * a single array of shape ``(samples, features, 2)`` (shap >= 0.45 TreeExplainer).

    The positive class is selected in both cases.

    Only the second form was previously handled. Under shap 0.45+ a binary tree model returns the
    3-D array, which this function passed straight through, so callers received a 3-D array where
    they expected 2-D and ``generate_shap_caption`` raised
    ``TypeError: only integer scalar arrays can be converted to a scalar index``. The advertised
    safe_shap_values -> to_matrix -> generate_shap_caption workflow was therefore broken for
    XGBoost and RandomForest, which are the models it is mainly used with.

    Multiclass output (more than two classes, in either shape) is returned unreduced: there is no
    single "positive" class to pick, and silently choosing one would be a wrong answer rather
    than an error.

    Parameters
    ----------
    shap_values : list or np.ndarray
        SHAP values from explainer

    Returns
    -------
    np.ndarray
        SHAP values as a matrix; 2-D for binary input, unchanged for multiclass.
    """
    # shap may return a list, one entry per class.
    if isinstance(shap_values, list) and len(shap_values) == 2:
        # choose positive class
        return np.array(shap_values[1])

    values = np.array(shap_values)

    # shap >= 0.45 returns (samples, features, n_classes) for binary tree models.
    if values.ndim == 3 and values.shape[-1] == 2:
        return values[:, :, 1]

    return values


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
    with _figure_scope():
        plt.figure(figsize=(6,5))
        shap.summary_plot(shap_values, X, plot_type="bar", show=False)
        plt.tight_layout()
        plt.savefig(output_path, dpi=dpi, bbox_inches="tight")


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
    with _figure_scope():
        plt.figure(figsize=(7,5))
        shap.summary_plot(shap_values, X, show=False)
        plt.tight_layout()
        plt.savefig(output_path, dpi=dpi, bbox_inches="tight")


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

