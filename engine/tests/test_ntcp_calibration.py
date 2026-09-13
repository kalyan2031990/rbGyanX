"""MLE NTCP calibration helpers."""

from __future__ import annotations

import numpy as np

from validation.ntcp_calibration import (
    _lkb_probit_ntcp,
    fit_lkb_parameters,
    fitted_params_to_yaml,
)


def _synthetic_dvh(geud_target: float = 50.0, n_bins: int = 20) -> dict:
    doses = np.linspace(0, 80, n_bins)
    vols = np.ones(n_bins) / n_bins
    return {"doses": doses, "vols": vols}


def test_lkb_probit_monotone():
    low = _lkb_probit_ntcp(30.0, 50.0, 0.15)
    high = _lkb_probit_ntcp(70.0, 50.0, 0.15)
    assert low < high


def test_fit_lkb_parameters_runs():
    n = 40
    rng = np.random.default_rng(0)
    dvh_list = [_synthetic_dvh() for _ in range(n)]
    outcomes = rng.binomial(1, 0.35, size=n).astype(float)
    fit = fit_lkb_parameters(dvh_list, outcomes, organ="Parotid_L", site="HN")
    assert fit.n_patients == n
    assert fit.TD50_gy > 0
    assert fit.m > 0
    yaml_text = fitted_params_to_yaml([fit], "HN")
    assert "Parotid_L" in yaml_text
