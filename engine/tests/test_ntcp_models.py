"""Unit tests for classical NTCP models and uncertainty."""

import pandas as pd
import numpy as np

import rbgyanx_engine.pipeline as pl
from radiobiology.ntcp import (
    calculate_ntcp_lkb_loglogit,
    calculate_ntcp_lkb_probit,
    calculate_ntcp_rs_poisson,
)
from radiobiology.bdvh import compute_eqd2_dvh
from radiobiology.geud_tcp import compute_geud
from config.site_ntcp_params import load_site_ntcp_params
from uncertainty.ntcp_mc import NTCPUncertaintyConfig, run_untcp


def test_lkb_loglogit_midpoint():
    ntcp = calculate_ntcp_lkb_loglogit(28.4, 28.4, 0.6)
    assert 0.45 < ntcp < 0.55


def test_lkb_probit_midpoint_exact():
    assert abs(calculate_ntcp_lkb_probit(45.0, 45.0, 0.18) - 0.5) < 1e-6


def test_lkb_probit_below_half_sub_td50():
    assert calculate_ntcp_lkb_probit(30.0, 45.0, 0.18) < 0.5


def test_lkb_probit_above_half_super_td50():
    assert calculate_ntcp_lkb_probit(60.0, 45.0, 0.18) > 0.5


def test_lkb_probit_increases_with_geud():
    low = calculate_ntcp_lkb_probit(30.0, 45.0, 0.18)
    high = calculate_ntcp_lkb_probit(60.0, 45.0, 0.18)
    assert high > low


def test_rs_poisson_bounded():
    dvh = pd.DataFrame({"dose_gy": [10, 20, 30], "volume_cm3": [1, 2, 3]})
    ntcp = calculate_ntcp_rs_poisson(dvh, D50=25.0, gamma=1.0, s=0.25)
    assert 0.0 <= ntcp <= 1.0


def test_hn_site_has_parotid():
    site = load_site_ntcp_params("HN")
    assert "Parotid_L" in site.organs


def test_bdvh_eqd2_greater_than_physical_for_sbrt():
    dvh = pd.DataFrame({"dose_gy": [18.0, 36.0, 54.0], "volume_frac": [0.4, 0.3, 0.3]})
    bdvh = compute_eqd2_dvh(dvh, n_fractions=3, alpha_beta_oar_gy=3.0)
    assert (bdvh["dose_gy"].values >= dvh["dose_gy"].values).all()


def test_bdvh_identity_at_2gy_per_fraction():
    dvh = pd.DataFrame({"dose_gy": [50.0, 50.0, 50.0], "volume_frac": [1 / 3] * 3})
    bdvh = compute_eqd2_dvh(dvh, n_fractions=25, alpha_beta_oar_gy=3.0)
    np.testing.assert_allclose(bdvh["dose_gy"].values, dvh["dose_gy"].values, rtol=1e-6)


def test_untcp_sd_nonzero_for_real_dvh():
    site = load_site_ntcp_params("HN")
    op = site.organs["Parotid_L"]
    dvh = pd.DataFrame({"dose_gy": [20.0, 28.0, 35.0], "volume_frac": [0.3, 0.4, 0.3]})
    result = run_untcp(dvh, op, config=NTCPUncertaintyConfig(n_samples=300, seed=0))
    assert result["uNTCP_LKB_loglogit"]["sd"] > 0
    assert result["uNTCP_LKB_loglogit"]["p5"] < result["uNTCP_LKB_loglogit"]["p95"]


def test_untcp_mean_close_to_deterministic():
    site = load_site_ntcp_params("HN")
    op = site.organs["Parotid_L"]
    dvh = pd.DataFrame({"dose_gy": [28.4], "volume_frac": [1.0]})
    geud = compute_geud(dvh, op.geud_a)
    nominal = calculate_ntcp_lkb_loglogit(geud, 28.4, 0.6)
    mc = run_untcp(dvh, op, config=NTCPUncertaintyConfig(n_samples=500, seed=0))
    assert abs(mc["uNTCP_LKB_loglogit"]["mean"] - nominal) < 0.10


def test_epv_gate_now_enforced_in_pipeline():
    src = pl.run_ml_xai_validation.__code__.co_consts
    joined = " ".join(str(x) for x in src if isinstance(x, str))
    assert "epv_threshold=1.0" not in joined
    assert "EPV_MINIMUM" in pl.__dict__
