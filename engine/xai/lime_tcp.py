# xai/lime_tcp.py

from __future__ import annotations

import pathlib
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def explain_patient_lime(
    model: Any,
    X_patient: np.ndarray,
    X_train: np.ndarray,
    feature_names: list[str],
    patient_id: str,
    output_path: str | pathlib.Path,
    num_features: int = 8,
    num_samples: int = 1000,
    dpi: int = 600,
) -> dict:
    """
    LIME local explanation for a single patient.
    """
    try:
        from lime.lime_tabular import LimeTabularExplainer
    except ImportError as exc:
        raise ImportError("lime>=0.2 required for LIME explanations.") from exc

    X_tr = np.asarray(X_train, dtype=float)
    X_pt = np.asarray(X_patient, dtype=float).flatten()

    explainer = LimeTabularExplainer(
        X_tr,
        feature_names=feature_names,
        mode="classification",
        discretize_continuous=True,
        random_state=42,
    )
    explanation = explainer.explain_instance(
        X_pt,
        model.predict_proba,
        num_features=num_features,
        num_samples=num_samples,
    )

    exp_list = explanation.as_list()
    feat_labels = [e[0] for e in exp_list]
    weights = [e[1] for e in exp_list]

    fig, ax = plt.subplots(figsize=(8, max(3, len(feat_labels) * 0.45)))
    colors = ["#d62728" if w >= 0 else "#1f77b4" for w in weights]
    ax.barh(range(len(feat_labels)), weights, color=colors)
    ax.set_yticks(range(len(feat_labels)))
    ax.set_yticklabels(feat_labels, fontsize=8)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("LIME weight (local linear approximation)")
    ax.set_title(f"Patient {patient_id} — LIME Local Explanation")
    plt.tight_layout()
    out = pathlib.Path(output_path)
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    return {
        "patient_id": patient_id,
        "feature_labels": feat_labels,
        "weights": weights,
        "predicted_prob": float(model.predict_proba(X_pt.reshape(1, -1))[0, 1]),
    }
