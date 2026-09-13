"""Pure-Python DVH DataFrames for radiobiology tests."""

import numpy as np
import pandas as pd


def make_uniform_dvh(dose_gy: float, n_bins: int = 100) -> pd.DataFrame:
    """100% of volume receives exactly dose_gy."""
    del n_bins
    return pd.DataFrame({"dose_gy": [dose_gy], "volume_frac": [1.0]})


def make_ramp_dvh(d_min: float, d_max: float, n_bins: int = 200) -> pd.DataFrame:
    """Uniform dose distribution from d_min to d_max Gy."""
    doses = np.linspace(d_min, d_max, n_bins)
    return pd.DataFrame(
        {"dose_gy": doses, "volume_frac": np.full(n_bins, 1.0 / n_bins)}
    )


def make_clinical_hn_dvh() -> pd.DataFrame:
    """Synthetic H&N GTV DVH: D95≈66, Dmean≈68, Dmax≈72 Gy (truncated Gaussian)."""
    doses = np.linspace(50.0, 80.0, 300)
    pdf = np.exp(-0.5 * ((doses - 68.0) / 3.5) ** 2)
    pdf = pdf / pdf.sum()
    return pd.DataFrame({"dose_gy": doses, "volume_frac": pdf})


def make_sbrt_dvh() -> pd.DataFrame:
    """Synthetic Lung SBRT DVH: uniform 54 Gy."""
    return make_uniform_dvh(54.0)
