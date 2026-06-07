"""Unit tests for Phase 3 uncertainty quantification."""

import math

import numpy as np
import pandas as pd
import pytest

from config.site_params import load_site_params


def make_uniform_dvh(total_dose_gy: float, n_bins: int = 50) -> pd.DataFrame:
    """Uniform DVH: all bins at the same dose."""
    doses = np.linspace(total_dose_gy * 0.95, total_dose_gy * 1.05, n_bins)
    vols = np.full(n_bins, 1.0 / n_bins)
    return pd.DataFrame({"dose_gy": doses, "volume_frac": vols})


# GROUP A — Parameter MC
def test_param_mc_mean_close_to_nominal_hn():
    sp = load_site_params("HN")
    dvh = make_uniform_dvh(70.0)
    from radiobiology.poisson_tcp import PoissonTCPCalculator
    from uncertainty.parameter_mc import ParamUncertaintyConfig, run_parameter_mc

    nominal = PoissonTCPCalculator().compute_tcp_dvh(dvh, 35, sp, "GTV")["tcp"]
    result = run_parameter_mc(
        dvh, 35, sp, "GTV", ParamUncertaintyConfig(n_samples=500, seed=0)
    )
    mc = result["TCP_Poisson_mc"]
    assert abs(mc["mean"] - nominal) < 0.05


def test_param_mc_sd_nonzero():
    sp = load_site_params("LUNG")
    dvh = make_uniform_dvh(54.0)
    from uncertainty.parameter_mc import ParamUncertaintyConfig, run_parameter_mc

    result = run_parameter_mc(
        dvh, 3, sp, "GTV", ParamUncertaintyConfig(n_samples=500, seed=1)
    )
    for key in ("TCP_Poisson_mc", "TCP_gEUD_mc", "TCP_Logistic_mc"):
        assert result[key]["sd"] > 0


def test_param_mc_percentile_ordering():
    sp = load_site_params("BREAST")
    dvh = make_uniform_dvh(50.0)
    from uncertainty.parameter_mc import ParamUncertaintyConfig, run_parameter_mc

    result = run_parameter_mc(
        dvh, 25, sp, "GTV", ParamUncertaintyConfig(n_samples=300, seed=2)
    )
    mc = result["TCP_Poisson_mc"]
    assert mc["p5"] <= mc["mean"] <= mc["p95"]


def test_param_mc_n_valid():
    sp = load_site_params("BRAIN")
    dvh = make_uniform_dvh(60.0)
    from uncertainty.parameter_mc import ParamUncertaintyConfig, run_parameter_mc

    cfg = ParamUncertaintyConfig(n_samples=200, seed=3)
    result = run_parameter_mc(dvh, 30, sp, "GTV", cfg)
    assert result["TCP_Poisson_mc"]["n_valid"] == 200


def test_param_mc_store_samples():
    sp = load_site_params("HN")
    dvh = make_uniform_dvh(66.0)
    from uncertainty.parameter_mc import ParamUncertaintyConfig, run_parameter_mc

    result = run_parameter_mc(
        dvh,
        33,
        sp,
        "GTV",
        ParamUncertaintyConfig(n_samples=100, seed=4, store_samples=True),
    )
    assert "_raw" in result
    assert len(result["_raw"]["TCP_Poisson"]) == 100


# GROUP B — Dosimetric Uncertainty
def test_dosimetric_mc_zero_sigma_equals_nominal():
    sp = load_site_params("HN")
    dvh = make_uniform_dvh(70.0)
    from radiobiology.poisson_tcp import PoissonTCPCalculator
    from uncertainty.dosimetric_uncertainty import (
        DosimetricUncertaintyConfig,
        run_dosimetric_mc,
    )

    nominal = PoissonTCPCalculator().compute_tcp_dvh(dvh, 35, sp, "GTV")["tcp"]
    result = run_dosimetric_mc(
        dvh,
        35,
        sp,
        "GTV",
        DosimetricUncertaintyConfig(
            systematic_dose_sigma_pct=0.001,
            random_dose_sigma_pct=0.001,
            n_samples=500,
            seed=0,
        ),
    )
    mc = result["TCP_Poisson_dose_mc"]
    assert abs(mc["mean"] - nominal) < 0.01


def test_dosimetric_mc_sd_nonzero():
    sp = load_site_params("LUNG")
    dvh = make_uniform_dvh(54.0)
    from uncertainty.dosimetric_uncertainty import (
        DosimetricUncertaintyConfig,
        run_dosimetric_mc,
    )

    result = run_dosimetric_mc(
        dvh, 3, sp, "GTV", DosimetricUncertaintyConfig(n_samples=500, seed=1)
    )
    assert result["TCP_Poisson_dose_mc"]["sd"] > 0


def test_dosimetric_sigma_eff_formula():
    from uncertainty.dosimetric_uncertainty import (
        DosimetricUncertaintyConfig,
        run_dosimetric_mc,
    )

    sp = load_site_params("HN")
    dvh = make_uniform_dvh(70.0)
    result = run_dosimetric_mc(
        dvh,
        35,
        sp,
        config=DosimetricUncertaintyConfig(
            systematic_dose_sigma_pct=2.0,
            random_dose_sigma_pct=1.5,
            n_samples=10,
            seed=0,
        ),
    )
    expected_sigma_eff_pct = math.sqrt(2.0**2 + 1.5**2 / 35) * 1.0
    assert abs(result["sigma_eff_pct"] - expected_sigma_eff_pct) < 1e-6


def test_dosimetric_mc_percentile_ordering():
    sp = load_site_params("BREAST")
    dvh = make_uniform_dvh(50.0)
    from uncertainty.dosimetric_uncertainty import run_dosimetric_mc

    result = run_dosimetric_mc(dvh, 25, sp, "GTV")
    mc = result["TCP_Poisson_dose_mc"]
    assert mc["p5"] <= mc["mean"] <= mc["p95"]


# GROUP C — Setup Error
def test_estimate_dose_gradient_positive():
    dvh = make_uniform_dvh(60.0)
    from uncertainty.setup_error import _estimate_dose_gradient

    g = _estimate_dose_gradient(dvh, penumbra_mm=10.0)
    assert g >= 0.0


def test_estimate_dose_gradient_flat_dvh():
    dvh = pd.DataFrame({"dose_gy": [60.0], "volume_frac": [1.0]})
    from uncertainty.setup_error import _estimate_dose_gradient

    g = _estimate_dose_gradient(dvh, penumbra_mm=10.0)
    assert g < 0.01


def test_setup_error_zero_shifts_nominal():
    sp = load_site_params("HN")
    dvh = make_uniform_dvh(70.0)
    from radiobiology.poisson_tcp import PoissonTCPCalculator
    from uncertainty.setup_error import SetupErrorConfig, run_setup_error_mc

    nominal = PoissonTCPCalculator().compute_tcp_dvh(dvh, 35, sp, "GTV")["tcp"]
    result = run_setup_error_mc(
        dvh,
        35,
        sp,
        "GTV",
        SetupErrorConfig(
            systematic_sigma_mm=0.0,
            random_sigma_mm=0.0,
            dose_gradient_gy_per_mm=0.5,
            n_samples=200,
            seed=0,
        ),
    )
    mc = result["TCP_Poisson_setup_mc"]
    assert abs(mc["mean"] - nominal) < 0.01


def test_setup_error_sigma_geom_formula():
    sp = load_site_params("HN")
    dvh = make_uniform_dvh(70.0)
    from uncertainty.setup_error import SetupErrorConfig, run_setup_error_mc

    result = run_setup_error_mc(
        dvh,
        35,
        sp,
        config=SetupErrorConfig(
            systematic_sigma_mm=3.0,
            random_sigma_mm=2.0,
            dose_gradient_gy_per_mm=0.5,
            n_samples=10,
            seed=0,
        ),
    )
    expected = math.sqrt(3.0**2 + 2.0**2 / 35)
    assert abs(result["sigma_geom_mm"] - expected) < 1e-6


def test_setup_error_sigma_dose_formula():
    sp = load_site_params("HN")
    dvh = make_uniform_dvh(70.0)
    from uncertainty.setup_error import SetupErrorConfig, run_setup_error_mc

    result = run_setup_error_mc(
        dvh,
        35,
        sp,
        config=SetupErrorConfig(
            systematic_sigma_mm=3.0,
            random_sigma_mm=2.0,
            dose_gradient_gy_per_mm=0.5,
            n_samples=10,
            seed=0,
        ),
    )
    expected_sigma_dose = 0.5 * math.sqrt(3.0**2 + 2.0**2 / 35)
    assert abs(result["sigma_dose_gy"] - expected_sigma_dose) < 1e-4


# GROUP D — Hypoxia
def test_hypoxia_hf_zero_equals_nominal():
    sp = load_site_params("HN")
    dvh = make_uniform_dvh(70.0)
    from radiobiology.poisson_tcp import PoissonTCPCalculator
    from uncertainty.hypoxia import HypoxiaConfig, apply_hypoxia_correction

    nominal = PoissonTCPCalculator().compute_tcp_dvh(dvh, 35, sp, "GTV")["tcp"]
    result = apply_hypoxia_correction(
        dvh, 35, sp, config=HypoxiaConfig(hypoxic_fraction=0.0)
    )
    assert abs(result["TCP_Poisson_hypoxia"] - nominal) < 1e-9


def test_hypoxia_oer_one_equals_nominal():
    sp = load_site_params("LUNG")
    dvh = make_uniform_dvh(54.0)
    from radiobiology.poisson_tcp import PoissonTCPCalculator
    from uncertainty.hypoxia import HypoxiaConfig, apply_hypoxia_correction

    nominal = PoissonTCPCalculator().compute_tcp_dvh(dvh, 3, sp, "GTV")["tcp"]
    result = apply_hypoxia_correction(
        dvh, 3, sp, config=HypoxiaConfig(hypoxic_fraction=0.20, oer=1.0)
    )
    assert abs(result["TCP_Poisson_hypoxia"] - nominal) < 1e-9


def test_hypoxia_reduces_tcp():
    sp = load_site_params("HN")
    dvh = make_uniform_dvh(70.0)
    from radiobiology.poisson_tcp import PoissonTCPCalculator
    from uncertainty.hypoxia import HypoxiaConfig, apply_hypoxia_correction

    nominal = PoissonTCPCalculator().compute_tcp_dvh(dvh, 35, sp, "GTV")["tcp"]
    result = apply_hypoxia_correction(
        dvh, 35, sp, config=HypoxiaConfig(hypoxic_fraction=0.30, oer=2.5)
    )
    assert result["TCP_Poisson_hypoxia"] <= nominal


def test_hypoxia_site_defaults():
    from uncertainty.hypoxia import SITE_HYPOXIC_FRACTION

    assert SITE_HYPOXIC_FRACTION["HN"] == pytest.approx(0.30)
    assert SITE_HYPOXIC_FRACTION["LUNG_SBRT"] == pytest.approx(0.20)
    assert SITE_HYPOXIC_FRACTION["BRAIN_GBM"] == pytest.approx(0.15)
    assert SITE_HYPOXIC_FRACTION["BREAST"] == pytest.approx(0.10)


def test_hypoxia_oer_parameter_scaling():
    sp = load_site_params("HN")
    dvh = make_uniform_dvh(70.0)
    from uncertainty.hypoxia import HypoxiaConfig, apply_hypoxia_correction

    result = apply_hypoxia_correction(
        dvh, 35, sp, config=HypoxiaConfig(hypoxic_fraction=0.30, oer=2.5)
    )
    assert result["alpha_hyp"] == pytest.approx(0.35 / 2.5, rel=1e-6)
    assert result["beta_hyp"] == pytest.approx(0.035 / 6.25, rel=1e-6)


def test_hypoxia_tcd50_eff():
    sp = load_site_params("HN")
    dvh = make_uniform_dvh(70.0)
    from uncertainty.hypoxia import HypoxiaConfig, apply_hypoxia_correction

    result = apply_hypoxia_correction(
        dvh, 35, sp, config=HypoxiaConfig(hypoxic_fraction=0.30, oer=2.5)
    )
    expected_tcd50 = sp.TCD50_gy * (1.0 + 0.30 * (2.5 - 1.0))
    assert result["TCD50_eff_geud"] == pytest.approx(expected_tcd50, rel=1e-6)


def test_hypoxia_geud_tcp_reduced():
    sp = load_site_params("HN")
    dvh = make_uniform_dvh(70.0)
    from radiobiology.geud_tcp import GEUDTCPCalculator
    from uncertainty.hypoxia import HypoxiaConfig, apply_hypoxia_correction

    nominal_geud = GEUDTCPCalculator().compute_tcp(dvh, sp)["tcp"]
    result = apply_hypoxia_correction(
        dvh, 35, sp, config=HypoxiaConfig(hypoxic_fraction=0.30, oer=2.5)
    )
    assert result["TCP_gEUD_hypoxia"] <= nominal_geud


def test_hypoxia_logistic_tcp_reduced():
    sp = load_site_params("BREAST")
    dvh = make_uniform_dvh(50.0)
    from radiobiology.logistic_tcp import LogisticTCPCalculator
    from uncertainty.hypoxia import HypoxiaConfig, apply_hypoxia_correction

    nominal_log = LogisticTCPCalculator().compute_tcp(dvh, sp)["tcp"]
    result = apply_hypoxia_correction(
        dvh, 25, sp, config=HypoxiaConfig(hypoxic_fraction=0.10, oer=2.5)
    )
    assert result["TCP_Logistic_hypoxia"] <= nominal_log
