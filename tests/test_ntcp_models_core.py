"""NTCP core re-exports must match engine implementations."""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine"))

from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit as eng_ll
from rbgyanx.core.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit as core_ll


def test_lkb_loglogit_core_matches_engine():
    geud, td50, gamma = 45.0, 50.0, 4.0
    assert eng_ll(geud, td50, gamma) == core_ll(geud, td50, gamma)


def test_empty_dvh_ntcp_metrics_nan():
    from radiobiology.ntcp_calculator import NTCPCalculator
    from config.site_ntcp_params import load_site_ntcp_params

    params = load_site_ntcp_params("HN")
    organ = params.organs["Parotid_L"]
    calc = NTCPCalculator()

    class EmptyDVH:
        dvh_object = None

    row = calc.compute_all(EmptyDVH(), {"n_fractions": 30, "dose_per_fraction_gy": 2.0}, organ, "HN")
    assert pd.isna(row["gEUD_gy"])
    assert pd.isna(row["NTCP_LKB_loglogit"])
