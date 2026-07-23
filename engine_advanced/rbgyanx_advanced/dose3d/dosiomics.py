"""Dosiomics from OAR dose voxels (§28)."""

from __future__ import annotations

import logging
import math

import numpy as np

logger = logging.getLogger(__name__)

try:
    from radiomics import featureextractor  # noqa: F401

    _PYRADIOMICS_AVAILABLE = True
except ImportError:
    _PYRADIOMICS_AVAILABLE = False


def _skewness(d: np.ndarray, mean: float, std: float) -> float:
    if std <= 0 or len(d) < 3:
        return math.nan
    return float(np.mean(((d - mean) / std) ** 3))


def _kurtosis(d: np.ndarray, mean: float, std: float) -> float:
    if std <= 0 or len(d) < 4:
        return math.nan
    return float(np.mean(((d - mean) / std) ** 4) - 3)


def _first_order_features(dose_voxels: np.ndarray | None) -> dict[str, float]:
    keys = (
        "dosio_mean",
        "dosio_std",
        "dosio_min",
        "dosio_max",
        "dosio_p10",
        "dosio_p25",
        "dosio_p75",
        "dosio_p90",
        "dosio_d2_gy",
        "dosio_d98_gy",
        "dosio_d50_gy",
        "dosio_skewness",
        "dosio_kurtosis",
        "dosio_energy",
        "dosio_uniformity",
        "dosio_entropy",
        "dosio_iqr",
        "dosio_cv",
        "dosio_hot_vol_frac",
    )
    if dose_voxels is None or len(dose_voxels) == 0:
        return {k: math.nan for k in keys}
    d = dose_voxels.astype(float)
    mean = float(np.mean(d))
    std = float(np.std(d))
    p = np.percentile(d, [2, 10, 25, 50, 75, 90, 98])
    hist, _ = np.histogram(d, bins=20, density=False)
    hist = hist / hist.sum() if hist.sum() > 0 else hist
    hist = hist[hist > 0]
    entropy = float(-np.sum(hist * np.log2(hist))) if len(hist) else math.nan
    uniformity = float(np.sum(hist**2)) if len(hist) else math.nan
    energy = float(np.sum(d**2) / len(d))
    hot_frac = float(np.mean(d >= 1.07 * mean)) if mean > 0 else math.nan
    return {
        "dosio_mean": mean,
        "dosio_std": std,
        "dosio_min": float(d.min()),
        "dosio_max": float(d.max()),
        "dosio_p10": float(p[1]),
        "dosio_p25": float(p[2]),
        "dosio_p75": float(p[4]),
        "dosio_p90": float(p[5]),
        "dosio_d2_gy": float(p[6]),
        "dosio_d98_gy": float(p[0]),
        "dosio_d50_gy": float(p[3]),
        "dosio_skewness": _skewness(d, mean, std),
        "dosio_kurtosis": _kurtosis(d, mean, std),
        "dosio_energy": energy,
        "dosio_uniformity": uniformity,
        "dosio_entropy": entropy,
        "dosio_iqr": float(p[4] - p[2]),
        "dosio_cv": std / mean if mean > 0 else math.nan,
        "dosio_hot_vol_frac": hot_frac,
    }


def extract_dosiomics_features(
    dose_voxels: np.ndarray | None,
    oar_name: str = "",
    use_pyradiomics: bool = False,
) -> dict[str, float]:
    prefix = f"dosio_{oar_name}_" if oar_name else "dosio_"
    features = _first_order_features(dose_voxels)
    return {prefix + k.replace("dosio_", ""): v for k, v in features.items()}
