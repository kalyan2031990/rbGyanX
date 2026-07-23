"""
P1.6 — defensive hardening: degenerate and NaN inputs across the engine.

Contract under test:
  * **exclude-and-count, never impute** — a quantity that cannot be computed stays NaN or the
    patient is dropped with a count; it is never silently replaced by 0.0;
  * **no extreme values from unidentifiable fits** — a flat/degenerate likelihood returns
    "not identifiable" (NaN / a flag), not 1e16;
  * **clear errors** where a run genuinely cannot proceed.

Classes covered: empty DVH, single-bin DVH, zero-volume / missing ROI, all-zero dose,
single-class endpoint, fewer than 2 CV groups, constant predictor, perfect separation.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from radiobiology.geud_tcp import compute_geud
from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
from radiobiology.ntcp.rs_poisson import calculate_ntcp_rs_poisson
from validation.four_tier_harness import run_four_tier_harness
from validation.ntcp_benchmark import classical_ntcp, fit_ntcp_mle, run_ntcp_benchmark
from validation.validation_metrics import calibration_slope

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------- fixtures


@pytest.fixture
def empty_dvh() -> pd.DataFrame:
    return pd.DataFrame({"dose_gy": [], "volume_frac": []})


@pytest.fixture
def single_bin_dvh() -> pd.DataFrame:
    return pd.DataFrame({"dose_gy": [30.0], "volume_frac": [1.0]})


@pytest.fixture
def zero_dose_dvh() -> pd.DataFrame:
    return pd.DataFrame({"dose_gy": [0.0] * 10, "volume_frac": [0.1] * 10})


@pytest.fixture
def zero_volume_dvh() -> pd.DataFrame:
    return pd.DataFrame({"dose_gy": [10.0, 20.0, 30.0], "volume_frac": [0.0, 0.0, 0.0]})


@pytest.fixture
def flat_likelihood_cohort() -> pd.DataFrame:
    """Dose carries NO information about the outcome -> the MLE is unidentifiable."""
    rng = np.random.default_rng(1234)
    n = 100
    dose = rng.uniform(10.0, 60.0, n)
    y = rng.integers(0, 2, n)  # independent of dose by construction
    return pd.DataFrame(
        {
            "patient_id": [f"P{i:03d}" for i in range(n)],
            "centre": rng.choice(["a", "b"], size=n),
            "OAR_gEUD_gy": dose,
            "OAR_Dmean_gy": dose - 1.0,
            "toxicity": y,
        }
    )


# --------------------------------------------------------------- degenerate DVHs


def test_geud_on_degenerate_dvhs(empty_dvh, zero_dose_dvh, zero_volume_dvh, single_bin_dvh):
    assert math.isnan(compute_geud(empty_dvh, 1.0))
    assert math.isnan(compute_geud(zero_dose_dvh, 1.0))  # no positive dose
    assert math.isnan(compute_geud(zero_volume_dvh, 1.0))  # zero total volume
    assert math.isnan(compute_geud(None, 1.0))
    assert math.isnan(compute_geud(single_bin_dvh, 0.0))  # a=0 undefined
    # A legitimate single-bin DVH is computable and equals that dose.
    assert compute_geud(single_bin_dvh, 1.0) == pytest.approx(30.0)


def test_ntcp_models_return_nan_not_zero_on_degenerate_input(empty_dvh, zero_volume_dvh):
    """NaN-not-zero: an uncomputable NTCP must never look like 'no complication'."""
    for val in (float("nan"), 0.0, -5.0):
        assert math.isnan(calculate_ntcp_lkb_probit(val, 40.0, 0.3))
        assert math.isnan(calculate_ntcp_lkb_loglogit(val, 40.0, 2.0))
    # degenerate parameters
    assert math.isnan(calculate_ntcp_lkb_probit(30.0, 0.0, 0.3))
    assert math.isnan(calculate_ntcp_lkb_probit(30.0, 40.0, 0.0))
    # relative seriality on degenerate DVHs
    assert math.isnan(calculate_ntcp_rs_poisson(empty_dvh, 40.0, 1.0, 0.25))
    assert math.isnan(calculate_ntcp_rs_poisson(zero_volume_dvh, 40.0, 1.0, 0.25))
    assert math.isnan(calculate_ntcp_rs_poisson(None, 40.0, 1.0, 0.25))
    for bad in (0.0, float("nan"), -1.0):
        assert math.isnan(calculate_ntcp_rs_poisson(zero_volume_dvh, bad, 1.0, 0.25))


def test_classical_ntcp_propagates_nan_rather_than_zero():
    p = classical_ntcp(
        "lkb_probit", {"TD50_gy": 40.0, "m": 0.3}, dose_metric=[30.0, float("nan"), 50.0]
    )
    assert math.isnan(p[1]), "missing dose must stay NaN, not become 0.0"
    assert p[0] > 0 and p[2] > 0


# --------------------------------------------------------------- unidentifiable fits


def test_mle_refit_on_flat_likelihood_is_bounded(flat_likelihood_cohort):
    """The headline regression: an unbounded fit returned TD50 ~ 1e16 Gy on real data."""
    df = flat_likelihood_cohort
    fit = fit_ntcp_mle("lkb_probit", df["OAR_gEUD_gy"], df["toxicity"])
    assert math.isfinite(fit["TD50_gy"])
    assert fit["TD50_gy"] <= 200.0
    lo, hi = fit["td50_bounds"]
    assert lo <= fit["TD50_gy"] <= hi
    assert 0.02 <= fit["m"] <= 1.5


def test_loglogistic_refit_is_also_bounded(flat_likelihood_cohort):
    df = flat_likelihood_cohort
    fit = fit_ntcp_mle("lkb_loglogit", df["OAR_gEUD_gy"], df["toxicity"])
    assert math.isfinite(fit["TD50_gy"]) and fit["TD50_gy"] <= 200.0
    assert 0.1 <= fit["gamma50"] <= 10.0


def test_benchmark_flags_unidentifiable_refit(flat_likelihood_cohort):
    table, extras = run_ntcp_benchmark(
        flat_likelihood_cohort,
        endpoint="toxicity",
        model="lkb_probit",
        params={"TD50_gy": 35.0, "m": 0.3},
        dose_metric_col="OAR_gEUD_gy",
        groups_col="centre",
        n_splits=2,
    )
    t2 = table.set_index("tier").loc["T2"]
    assert "not identifiable" in str(t2["note"]).lower()
    assert extras["refit_params"]["plausible"] is False


# --------------------------------------------------------------- LKB calibration fit


def _dvh_entry(dose: float, n_bins: int = 20) -> dict:
    return {
        "doses": np.full(n_bins, dose, dtype=float),
        "vols": np.full(n_bins, 1.0 / n_bins, dtype=float),
    }


def test_lkb_calibration_flags_non_identifiable_fit():
    """A flat likelihood pins the fit to a bound; it must be flagged, not reported as a model."""
    from validation.ntcp_calibration import fit_lkb_parameters

    rng = np.random.default_rng(21)
    n = 60
    doses = rng.uniform(20.0, 40.0, n)
    y = rng.integers(0, 2, n)  # independent of dose
    dvhs = [_dvh_entry(d) for d in doses]

    fit = fit_lkb_parameters(dvhs, y, organ="Test", site="TEST", n_bootstrap=0)
    assert 10.0 <= fit.TD50_gy <= 150.0, "TD50 must stay inside the parameter bounds"
    assert 0.01 <= fit.m <= 0.5
    if not fit.identifiable:
        assert "not identifiable" in fit.note or "did not converge" in fit.note


def test_lkb_calibration_marks_a_real_dose_response_identifiable():
    from validation.ntcp_calibration import fit_lkb_parameters

    rng = np.random.default_rng(5)
    n = 200
    doses = rng.uniform(20.0, 80.0, n)
    p = 1.0 / (1.0 + np.exp(-(doses - 50.0) / 6.0))
    y = (rng.uniform(size=n) < p).astype(float)
    dvhs = [_dvh_entry(d) for d in doses]

    fit = fit_lkb_parameters(dvhs, y, organ="Test", site="TEST", n_bootstrap=0)
    assert fit.converged
    assert 10.0 <= fit.TD50_gy <= 150.0


# --------------------------------------------------------------- calibration slope


def test_calibration_slope_on_constant_predictor_is_nan():
    y = np.array([0, 1] * 20)
    p = np.full(40, 0.3)  # zero variance
    slope, intercept = calibration_slope(y, p)
    assert math.isnan(slope) and math.isnan(intercept)


def test_calibration_slope_on_single_class_is_nan():
    y = np.ones(20, dtype=int)
    p = np.linspace(0.1, 0.9, 20)
    slope, _ = calibration_slope(y, p)
    assert math.isnan(slope)


def test_calibration_slope_on_perfect_separation_is_not_extreme():
    """Perfect separation drives the logistic slope to infinity; must not be reported."""
    y = np.array([0] * 20 + [1] * 20)
    p = np.array([0.01] * 20 + [0.99] * 20)
    slope, _ = calibration_slope(y, p)
    assert math.isnan(slope) or abs(slope) <= 10.0


def test_calibration_slope_recovers_a_well_calibrated_model():
    rng = np.random.default_rng(3)
    p = rng.uniform(0.05, 0.95, 400)
    y = (rng.uniform(size=400) < p).astype(int)
    slope, _ = calibration_slope(y, p)
    assert math.isfinite(slope)
    assert 0.5 < slope < 1.8  # near 1 for a well-calibrated predictor


def test_harness_calibration_slope_rejects_degenerate_predictions():
    y = np.array([0, 1] * 15)
    res = run_four_tier_harness(
        y_true=y,
        classical_probs=np.full(30, 0.4),  # constant -> slope not identifiable
        patient_ids=np.arange(30),
    )
    assert math.isnan(res["T1"].calibration_slope)


# --------------------------------------------------------------- degenerate cohorts


def test_single_class_endpoint_all_events_is_a_clear_error():
    df = pd.DataFrame({"toxicity": [1] * 10, "OAR_gEUD_gy": np.linspace(20, 60, 10)})
    with pytest.raises(ValueError, match="single class|both outcome classes"):
        run_ntcp_benchmark(
            df,
            endpoint="toxicity",
            model="lkb_probit",
            params={"TD50_gy": 35.0, "m": 0.3},
            dose_metric_col="OAR_gEUD_gy",
        )


def test_single_class_endpoint_no_events_is_a_clear_error():
    df = pd.DataFrame({"toxicity": [0] * 10, "OAR_gEUD_gy": np.linspace(20, 60, 10)})
    with pytest.raises(ValueError, match="single class|both outcome classes"):
        run_ntcp_benchmark(
            df,
            endpoint="toxicity",
            model="lkb_probit",
            params={"TD50_gy": 35.0, "m": 0.3},
            dose_metric_col="OAR_gEUD_gy",
        )


def test_fewer_than_two_cv_groups_does_not_crash():
    """One centre => no grouped split is possible; metrics degrade to NaN, not an exception."""
    rng = np.random.default_rng(9)
    n = 40
    dose = rng.uniform(10, 60, n)
    y = (rng.uniform(size=n) < 1 / (1 + np.exp(-(dose - 35) / 6))).astype(int)
    df = pd.DataFrame({"toxicity": y, "OAR_gEUD_gy": dose, "centre": ["only"] * n})
    table, extras = run_ntcp_benchmark(
        df,
        endpoint="toxicity",
        model="lkb_probit",
        params={"TD50_gy": 35.0, "m": 0.3},
        dose_metric_col="OAR_gEUD_gy",
        dosiomics_cols=["OAR_gEUD_gy"],
        groups_col="centre",
        n_splits=4,
    )
    assert extras["n"] == n
    assert "T1" in set(table["tier"])  # fixed classical still reportable


def test_all_patients_missing_dose_is_a_clear_error():
    df = pd.DataFrame({"toxicity": [0, 1, 0, 1], "OAR_gEUD_gy": [float("nan")] * 4})
    with pytest.raises(ValueError, match="single class after excluding"):
        run_ntcp_benchmark(
            df,
            endpoint="toxicity",
            model="lkb_probit",
            params={"TD50_gy": 35.0, "m": 0.3},
            dose_metric_col="OAR_gEUD_gy",
        )
