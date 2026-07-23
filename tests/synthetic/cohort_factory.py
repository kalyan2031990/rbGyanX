"""Synthetic outcome cohorts with planted LKB ground truth."""

from __future__ import annotations

import numpy as np
import pandas as pd

from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit


def planted_lkb_cohort(
    n_patients: int = 40,
    td50: float = 26.0,
    m: float = 0.40,
    n_serial: float = 0.45,
    seed: int = 42,
) -> tuple[pd.DataFrame, dict]:
    """
    Generate (geud, binary toxicity) from known LKB probit parameters.

    Returns cohort DataFrame and planted truth dict for recovery tests.
    """
    rng = np.random.default_rng(seed)
    geuds = rng.uniform(15.0, 45.0, size=n_patients)
    probs = [calculate_ntcp_lkb_probit(g, td50, m) for g in geuds]
    outcomes = rng.binomial(1, probs).astype(int)
    df = pd.DataFrame(
        {
            "patient_id": [f"P{i:03d}" for i in range(n_patients)],
            "geud_gy": geuds,
            "Observed_Toxicity": outcomes,
            "organ": "Parotid_L",
        }
    )
    truth = {"TD50_gy": td50, "m": m, "n": n_serial, "n_events": int(outcomes.sum())}
    return df, truth


def dvh_list_from_geuds(geuds: np.ndarray, n_bins: int = 50) -> list[dict]:
    """Uniform DVH per patient at geud (for MLE calibration tests)."""
    dvh_list = []
    for g in geuds:
        doses = np.full(n_bins, float(g))
        vols = np.ones(n_bins) / n_bins
        dvh_list.append({"doses": doses, "vols": vols})
    return dvh_list
