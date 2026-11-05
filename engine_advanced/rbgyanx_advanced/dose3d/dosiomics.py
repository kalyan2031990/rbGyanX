"""Dosiomics from OAR dose voxels (§28).

Scope note: this module computes **first-order dose statistics only** -- mean, SD, min, max,
percentiles, D2/D50/D98, skewness, kurtosis, energy, uniformity, entropy, IQR, CV and a hot-volume
fraction. It computes **no texture features**. There is no GLCM, GLRLM, GLSZM, NGLDM or NGTDM
implementation anywhere in this release, for dose or for CT.

An earlier version of this docstring said the 3-D texture dosiomics "are computed by this module",
which was false and contradicted the sentence before it (defect #53). The claim arose from
rewriting a pointer to ``analysis/dosiomics/`` when that directory was removed; the pointer went,
the capability never existed here, and the sentence should have gone too rather than being
re-aimed at this module.

Features computed from generated voxels are surrogates, not dosiomics. Pass ``production=True``
(or a ``dose_source``) to have that enforced rather than trusted.
"""

from __future__ import annotations

import logging
import math

import numpy as np

from rbgyanx_advanced.dose3d.dose_grid_extractor import (
    SOURCE_NOT_AVAILABLE,
    assert_production_dose_source,
)

logger = logging.getLogger(__name__)


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
    *,
    dose_source: str | None = None,
    production: bool = False,
) -> dict[str, float]:
    """First-order dose features for one OAR.

    ``dose_source`` records where the voxels came from (see ``dose_grid_extractor``). When
    ``production=True`` the source must be a real RTDOSE grid, otherwise
    :class:`SyntheticDoseInProductionError` is raised - a production run fails rather than emitting
    surrogate features that look like measurements.

    ``use_pyradiomics`` has no implementation behind it and must be left ``False``. It was
    previously accepted and silently ignored (defect #54): a caller asking for pyradiomics-backed
    texture features received the first-order dictionary instead, with nothing in the return value
    or the log to say so. Passing ``True`` now raises :class:`NotImplementedError`, on the same
    principle as ``production=True`` -- refuse rather than return something that looks like the
    measurement that was asked for.
    """
    if use_pyradiomics:
        raise NotImplementedError(
            "use_pyradiomics=True is not implemented: this module computes first-order dose "
            "statistics only and has no texture-feature backend (defect #54). Leave it False; "
            "passing True previously returned first-order features with no indication that the "
            "request had been ignored."
        )
    if production:
        assert_production_dose_source(
            dose_source if dose_source is not None else SOURCE_NOT_AVAILABLE,
            context=f"dosiomics[{oar_name or 'unnamed_oar'}]",
        )
    prefix = f"dosio_{oar_name}_" if oar_name else "dosio_"
    features = _first_order_features(dose_voxels)
    return {prefix + k.replace("dosio_", ""): v for k, v in features.items()}
