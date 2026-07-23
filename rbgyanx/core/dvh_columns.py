"""Normalize DVH DataFrame column names for core TCP/NTCP calculators."""

from __future__ import annotations

import pandas as pd


def normalize_dvh_columns(dvh: pd.DataFrame) -> pd.DataFrame:
    """Return copy with ``dose_gy`` and ``volume_cm3`` (or ``volume_frac``)."""
    if dvh is None or dvh.empty:
        return dvh
    df = dvh.copy()
    dose_aliases = ("dose_gy", "Dose[Gy]", "Dose_Gy", "dose", "Dose")
    vol_aliases = ("volume_cm3", "Volume[cm3]", "Volume_cm3", "volume_frac", "Volume[%]", "volume")
    dose_col = next((c for c in dose_aliases if c in df.columns), None)
    vol_col = next((c for c in vol_aliases if c in df.columns), None)
    if dose_col is None or vol_col is None:
        raise ValueError(
            "Could not find dose/volume columns. "
            f"Have: {list(df.columns)}; need dose (e.g. dose_gy) and volume (e.g. volume_cm3)."
        )
    if dose_col != "dose_gy":
        df["dose_gy"] = df[dose_col].astype(float)
    if vol_col != "volume_cm3" and vol_col != "volume_frac":
        df["volume_cm3"] = df[vol_col].astype(float)
    elif vol_col == "volume_frac" and "volume_cm3" not in df.columns:
        df["volume_cm3"] = df["volume_frac"].astype(float)
    return df
