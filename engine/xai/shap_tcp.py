# xai/shap_tcp.py

from __future__ import annotations

import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def plot_shap_global(
    shap_values: np.ndarray,
    feature_names: list[str],
    output_path: str | pathlib.Path,
    title: str = "Global SHAP Feature Importance",
    top_n: int = 15,
    dpi: int = 600,
) -> pathlib.Path:
    """
    Bar chart: mean |SHAP value| per feature, sorted descending.
    """
    mean_abs = np.mean(np.abs(shap_values), axis=0)
    order = np.argsort(mean_abs)[::-1][:top_n]
    feats = [feature_names[i] for i in order]
    vals = mean_abs[order]

    fig, ax = plt.subplots(figsize=(8, max(4, top_n * 0.35)))
    ax.barh(range(len(feats)), vals[::-1], color="steelblue")
    ax.set_yticks(range(len(feats)))
    ax.set_yticklabels(feats[::-1], fontsize=8)
    ax.set_xlabel("Mean |SHAP value|")
    ax.set_title(title)
    ax.invert_yaxis()
    plt.tight_layout()
    out = pathlib.Path(output_path)
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_shap_waterfall(
    shap_values_patient: np.ndarray,
    feature_names: list[str],
    feature_values: np.ndarray,
    expected_value: float,
    predicted_prob: float,
    patient_id: str,
    output_path: str | pathlib.Path,
    dpi: int = 600,
) -> pathlib.Path:
    """
    Waterfall plot for a single patient showing SHAP contributions.
    """
    n_features = len(feature_names)
    order = np.argsort(np.abs(shap_values_patient))[::-1]
    feats = [feature_names[i] for i in order]
    shap_vals = shap_values_patient[order]
    feat_vals = feature_values[order]

    fig, ax = plt.subplots(figsize=(9, max(4, n_features * 0.4)))
    colors = ["#d62728" if v >= 0 else "#1f77b4" for v in shap_vals]
    ax.barh(range(n_features), shap_vals, color=colors)
    ax.set_yticks(range(n_features))
    labels = [f"{feats[i]} = {feat_vals[i]:.3g}" for i in range(n_features)]
    ax.set_yticklabels(labels[::-1] if False else labels, fontsize=7)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("SHAP value (contribution to log-odds)")
    ax.set_title(
        f"Patient {patient_id} — SHAP Waterfall\n"
        f"Baseline: {expected_value:.3f} | Predicted TCP: {predicted_prob:.3f}"
    )
    plt.tight_layout()
    out = pathlib.Path(output_path)
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out


def verify_shap_consistency(
    shap_values: np.ndarray,
    expected_value: float,
    predicted_probs: np.ndarray,
    tolerance: float = 0.01,
) -> dict:
    """
    Verify SHAP additivity: expected_value + Σ SHAP_i ≈ log-odds(predicted_prob).
    """
    log_odds = np.log(
        np.clip(predicted_probs, 1e-9, 1 - 1e-9)
        / (1 - np.clip(predicted_probs, 1e-9, 1 - 1e-9))
    )
    reconstructed = expected_value + shap_values.sum(axis=1)
    deviations = np.abs(reconstructed - log_odds)
    violations = int(np.sum(deviations > tolerance))
    return {
        "all_pass": violations == 0,
        "max_deviation": float(np.max(deviations)),
        "n_violations": violations,
        "n_patients": len(predicted_probs),
    }
