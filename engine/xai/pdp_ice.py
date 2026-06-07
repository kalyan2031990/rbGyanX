# xai/pdp_ice.py

from __future__ import annotations

import pathlib
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def compute_pdp_ice(
    model: Any,
    X: np.ndarray,
    feature_idx: int,
    grid_points: int = 50,
    percentile_range: tuple[float, float] = (5.0, 95.0),
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute PDP and ICE values for one feature.
    """
    X_arr = np.asarray(X, dtype=float)
    lo = float(np.percentile(X_arr[:, feature_idx], percentile_range[0]))
    hi = float(np.percentile(X_arr[:, feature_idx], percentile_range[1]))
    grid = np.linspace(lo, hi, grid_points)

    n_samples = X_arr.shape[0]
    ice = np.zeros((n_samples, grid_points))

    for j, g in enumerate(grid):
        X_copy = X_arr.copy()
        X_copy[:, feature_idx] = g
        ice[:, j] = model.predict_proba(X_copy)[:, 1]

    pdp = ice.mean(axis=0)
    return grid, pdp, ice


def plot_pdp_ice(
    grid: np.ndarray,
    pdp: np.ndarray,
    ice: np.ndarray,
    feature_name: str,
    output_path: str | pathlib.Path,
    classical_tcp_fn: Callable[[np.ndarray], np.ndarray] | None = None,
    classical_label: str = "Classical TCP",
    title: str | None = None,
    dpi: int = 600,
) -> pathlib.Path:
    """
    Plot PDP (thick line) + ICE curves (thin, semi-transparent) for one feature.
    """
    fig, ax = plt.subplots(figsize=(7, 4.5))

    for i in range(min(ice.shape[0], 100)):
        ax.plot(grid, ice[i], color="grey", alpha=0.15, linewidth=0.6)

    ax.plot(grid, pdp, color="steelblue", linewidth=2.5, label="PDP (mean)")

    if classical_tcp_fn is not None:
        try:
            classical_vals = np.asarray(classical_tcp_fn(grid), dtype=float)
            ax.plot(
                grid,
                classical_vals,
                color="tomato",
                linewidth=2.0,
                linestyle="--",
                label=classical_label,
            )
        except Exception:
            pass

    ax.set_xlabel(feature_name)
    ax.set_ylabel("Predicted TCP (P local control)")
    ax.set_ylim(0, 1)
    ax.set_title(title or f"PDP+ICE — {feature_name}")
    ax.legend(fontsize=8)
    plt.tight_layout()
    out = pathlib.Path(output_path)
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out
