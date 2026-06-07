"""Radiobiology TCP calculation engine."""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def dvh_object_to_dataframe(dvh) -> pd.DataFrame:
    """
    Convert a dicompyler-core DVH object to the standard differential DVH DataFrame.

    Columns: dose_gy (bin centre, Gy), volume_frac (sums to 1.0).
    """
    if dvh is None:
        return pd.DataFrame(columns=["dose_gy", "volume_frac"])

    diff = dvh.differential if getattr(dvh, "dvh_type", "") != "differential" else dvh
    counts = np.asarray(diff.counts, dtype=float)
    bins = np.asarray(diff.bins, dtype=float)

    if counts.size == 0 or bins.size < 2:
        return pd.DataFrame(columns=["dose_gy", "volume_frac"])

    dose_scale = 0.01 if str(getattr(dvh, "dose_units", "Gy")).lower() == "cgy" else 1.0
    centres = 0.5 * (bins[1:] + bins[:-1]) * dose_scale
    centres = centres[: counts.size]

    total = counts.sum()
    if total <= 0:
        volume_frac = counts
    else:
        volume_frac = counts / total

    frame = pd.DataFrame({"dose_gy": centres, "volume_frac": volume_frac})
    frame = frame[frame["volume_frac"] > 0].reset_index(drop=True)
    if frame["volume_frac"].sum() > 0:
        frame["volume_frac"] = frame["volume_frac"] / frame["volume_frac"].sum()
    return frame


from radiobiology.geud_tcp import GEUDTCPCalculator, compute_geud, geud_tcp_niemierko
from radiobiology.logistic_tcp import LogisticTCPCalculator, logistic_tcp
from radiobiology.lq_model import (
    bed,
    eqd2,
    eqd2_usc,
    survival_fraction,
    survival_fraction_lq,
    survival_fraction_usc,
    treatment_time_days,
)
from radiobiology.poisson_tcp import PoissonTCPCalculator
from radiobiology.tcp_calculator import TCPCalculator
from radiobiology.zaider_minerbo import ZMTCPCalculator

__all__ = [
    "GEUDTCPCalculator",
    "LogisticTCPCalculator",
    "PoissonTCPCalculator",
    "TCPCalculator",
    "ZMTCPCalculator",
    "bed",
    "compute_geud",
    "dvh_object_to_dataframe",
    "eqd2",
    "eqd2_usc",
    "geud_tcp_niemierko",
    "logistic_tcp",
    "survival_fraction",
    "survival_fraction_lq",
    "survival_fraction_usc",
    "treatment_time_days",
]
