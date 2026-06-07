"""
Biological DVH (bDVH) — EQD2 correction of physical DVH per OAR.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

DEFAULT_OAR_ALPHA_BETA: dict[str, float] = {
    "SpinalCord": 3.0,
    "Brainstem": 2.0,
    "OpticChiasm": 2.0,
    "OpticNerve_L": 2.0,
    "OpticNerve_R": 2.0,
    "Parotid_L": 3.0,
    "Parotid_R": 3.0,
    "Submandibular_L": 3.0,
    "Submandibular_R": 3.0,
    "LungTotal": 3.0,
    "Lung_L": 3.0,
    "Lung_R": 3.0,
    "Heart": 3.0,
    "Esophagus": 3.0,
    "Cochlea_L": 3.0,
    "Cochlea_R": 3.0,
    "Hippocampus_L": 2.0,
    "Hippocampus_R": 2.0,
    "LAD": 3.0,
    "Lung_Ipsi": 3.0,
}


def compute_eqd2_dvh(
    dvh_df: pd.DataFrame,
    n_fractions: int,
    alpha_beta_oar_gy: float,
) -> pd.DataFrame:
    """Convert a physical differential DVH to EQD2 DVH."""
    if dvh_df is None or dvh_df.empty:
        return dvh_df
    if n_fractions <= 0 or alpha_beta_oar_gy <= 0:
        raise ValueError("n_fractions and alpha_beta_oar_gy must both be > 0.")

    physical_dose = np.asarray(dvh_df["dose_gy"], dtype=float)
    dpf = physical_dose / n_fractions
    eqd2 = physical_dose * (dpf + alpha_beta_oar_gy) / (2.0 + alpha_beta_oar_gy)
    eqd2 = np.where(physical_dose <= 0, 0.0, eqd2)

    result = dvh_df.copy()
    result["dose_gy"] = eqd2
    return result


def get_alpha_beta_for_organ(
    canonical_name: str,
    organ_params_alpha_beta: float | None = None,
) -> float:
    """Return OAR alpha/beta from YAML entry or defaults."""
    if organ_params_alpha_beta is not None and organ_params_alpha_beta > 0:
        return float(organ_params_alpha_beta)
    ab = DEFAULT_OAR_ALPHA_BETA.get(canonical_name)
    if ab is not None:
        return float(ab)
    logging.getLogger(__name__).warning(
        "No alpha/beta found for OAR '%s'; using 3.0 Gy default.", canonical_name
    )
    return 3.0
