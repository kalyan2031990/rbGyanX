"""DVH dose-heterogeneity features (avoids circular imports with calculators)."""

from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _safe_skewness(arr: np.ndarray) -> float:
    """Third standardised moment. Returns 0.0 for near-constant arrays (no scipy)."""
    if len(arr) < 4:
        return math.nan
    std = float(np.std(arr))
    if std < 1e-6:
        return 0.0
    return float(np.mean(((arr - np.mean(arr)) / std) ** 3))


def _safe_kurtosis(arr: np.ndarray) -> float:
    """Excess kurtosis (Fisher). Returns 0.0 for near-constant arrays (no scipy)."""
    if len(arr) < 4:
        return math.nan
    std = float(np.std(arr))
    if std < 1e-6:
        return 0.0
    return float(np.mean(((arr - np.mean(arr)) / std) ** 4) - 3.0)


def compute_dvh_shape_features(dvh_df: pd.DataFrame, structure_name: str = "") -> dict:
    """Dose-heterogeneity statistics from a differential DVH (CURSOR_FIXES 17)."""
    keys = (
        "D2_gy", "D50_gy", "D98_gy", "D2_D98_ratio",
        "dose_skewness", "dose_kurtosis", "V95_rx_frac", "dose_std_gy",
    )
    nan_row = {k: math.nan for k in keys}
    if dvh_df is None or dvh_df.empty:
        return nan_row

    dose_col = "dose_gy" if "dose_gy" in dvh_df.columns else dvh_df.columns[0]
    vol_col  = next(
        (c for c in ("volume_frac", "volume_cm3", "Volume[%]") if c in dvh_df.columns),
        None,
    )
    if vol_col is None:
        return nan_row

    doses = np.asarray(dvh_df[dose_col], dtype=float)
    vols  = np.asarray(dvh_df[vol_col], dtype=float)
    total = vols.sum()
    if total <= 0:
        return nan_row
    vols = vols / total

    order   = np.argsort(doses)
    d_sorted = doses[order]
    v_sorted = vols[order]
    cum     = np.cumsum(v_sorted)

    def weighted_percentile(p: float) -> float:
        idx = int(np.searchsorted(cum, p / 100.0, side="left"))
        return float(d_sorted[min(idx, len(d_sorted) - 1)])

    d2   = weighted_percentile(98)
    d50  = weighted_percentile(50)
    d98  = weighted_percentile(2)
    dmean     = float((doses * vols).sum())
    dose_std  = float(np.sqrt(((doses - dmean) ** 2 * vols).sum()))
    counts    = np.maximum(np.round(vols * 1000).astype(int), 0)
    sample    = np.repeat(doses, counts) if counts.sum() > 0 else doses
    sk        = _safe_skewness(sample)
    ku        = _safe_kurtosis(sample)
    v95       = float(vols[doses >= 0.95 * dmean].sum()) if dmean > 0 else math.nan

    return {
        "D2_gy":       d2,
        "D50_gy":      d50,
        "D98_gy":      d98,
        "D2_D98_ratio": d2 / d98 if d98 > 0 else math.nan,
        "dose_skewness":  sk,
        "dose_kurtosis":  ku,
        "V95_rx_frac":    v95,
        "dose_std_gy":    dose_std,
    }


def extract_3d_dose_array(
    dicom_folder: Path,
    structure_name: str,
    voxel_size_mm: float = 3.0,
) -> np.ndarray | None:
    """Stub for 3D dose (Section 20); full path in rbgyanx_advanced.dose3d."""
    logger.info(
        "extract_3d_dose_array: stub -- use rbgyanx_advanced.dose3d in ADVANCED mode."
    )
    return None
