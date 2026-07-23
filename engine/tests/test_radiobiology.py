"""Unit tests for Phase 2 radiobiology engine."""

from __future__ import annotations

import copy
import math

import numpy as np
import pandas as pd
import pytest

from config.site_params import SITE_PARAMS
from radiobiology.geud_tcp import GEUDTCPCalculator, compute_geud, geud_tcp_niemierko
from radiobiology.logistic_tcp import LogisticTCPCalculator, logistic_tcp
from radiobiology.lq_model import (
    bed,
    eqd2,
    survival_fraction_lq,
    survival_fraction_usc,
    treatment_time_days,
)
from radiobiology.poisson_tcp import PoissonTCPCalculator
from radiobiology.tcp_calculator import TCPCalculator
from radiobiology.zaider_minerbo import ZMTCPCalculator
from synthetic_data.dvh_fixtures import (
    make_ramp_dvh,
    make_sbrt_dvh,
    make_uniform_dvh,
)


# Group 1 — LQ model
def test_bed_standard_fractionation():
    result = bed(60.0, 2.0, 10.0)
    assert abs(result - 72.0) < 0.01


def test_bed_sbrt():
    result = bed(48.0, 12.0, 10.0)
    assert abs(result - 105.6) < 0.01


def test_eqd2_already_2gy():
    result = eqd2(60.0, 2.0, 10.0)
    assert abs(result - 60.0) < 0.01


def test_eqd2_breast_hypofrac():
    result = eqd2(40.05, 2.67, 3.5)
    assert 44.0 <= result <= 46.0


def test_eqd2_lung_sbrt():
    result = eqd2(45.0, 15.0, 10.0)
    assert abs(result - 93.75) < 0.1


def test_sf_lq_known_value():
    sf = survival_fraction_lq(2.0, 0.35, 0.035)
    assert abs(sf - np.exp(-0.84)) < 1e-6


def test_usc_equals_lq_below_transition():
    for d in [1.0, 3.0, 5.0, 9.9]:
        assert (
            abs(
                survival_fraction_usc(d, 0.30, 0.034, d_transition_gy=10.0)
                - survival_fraction_lq(d, 0.30, 0.034)
            )
            < 1e-9
        )


def test_usc_equals_lq_at_transition():
    d_t = 10.0
    usc = survival_fraction_usc(d_t, 0.30, 0.034, d_t)
    lq = survival_fraction_lq(d_t, 0.30, 0.034)
    assert abs(usc - lq) < 1e-9


def test_usc_greater_than_lq_above_transition():
    for d in [11.0, 15.0, 18.0, 24.0]:
        assert survival_fraction_usc(d, 0.30, 0.034, 10.0) > survival_fraction_lq(
            d, 0.30, 0.034
        ), f"USC should exceed LQ at d={d} Gy"


def test_treatment_time_standard():
    t_val = treatment_time_days(30, fractions_per_week=5.0)
    assert 42.0 <= t_val <= 43.0


def test_treatment_time_srs():
    assert treatment_time_days(1) == 1.0


# Group 2 — Poisson TCP
def test_poisson_tcp_increases_with_dose():
    hn = SITE_PARAMS["HN"]
    tcp_60 = PoissonTCPCalculator().compute_tcp_uniform(60.0, 30, hn)["tcp"]
    tcp_70 = PoissonTCPCalculator().compute_tcp_uniform(70.0, 35, hn)["tcp"]
    assert tcp_70 > tcp_60, "TCP must increase with dose"


def test_poisson_tcp_repop_lowers_tcp():
    hn = SITE_PARAMS["HN"]
    tcp_short = PoissonTCPCalculator().compute_tcp_uniform(
        60.0, 30, hn, treatment_time_days=42.0
    )["tcp"]
    tcp_long = PoissonTCPCalculator().compute_tcp_uniform(
        60.0, 30, hn, treatment_time_days=70.0
    )["tcp"]
    assert tcp_short >= tcp_long, "Longer treatment (more repop) must lower TCP"


def test_poisson_tcp_uniform_equals_dvh():
    hn = SITE_PARAMS["HN"]
    calc = PoissonTCPCalculator()
    dvh = make_uniform_dvh(60.0)
    tcp_uniform = calc.compute_tcp_uniform(60.0, 30, hn)["tcp"]
    tcp_dvh = calc.compute_tcp_dvh(dvh, 30, hn)["tcp"]
    assert abs(tcp_uniform - tcp_dvh) < 0.01


def test_poisson_usc_lowers_tcp_vs_lq():
    lung = SITE_PARAMS["LUNG"]
    calc = PoissonTCPCalculator()
    dvh = make_uniform_dvh(54.0)
    lung_forced_lq = lung._replace(lq_valid_max_dpf_gy=99.0)
    tcp_usc = calc.compute_tcp_dvh(dvh, 3, lung)["tcp"]
    tcp_lq = calc.compute_tcp_dvh(dvh, 3, lung_forced_lq)["tcp"]
    assert tcp_lq >= tcp_usc


# Group 3 — Zaider-Minerbo
def test_zm_tcp_not_less_than_poisson():
    hn = SITE_PARAMS["HN"]
    p_calc = PoissonTCPCalculator()
    zm_calc = ZMTCPCalculator(dead_fraction=0.85, t_obs_days=730)
    dvh = make_uniform_dvh(60.0)
    tcp_poisson = p_calc.compute_tcp_dvh(dvh, 30, hn)["tcp"]
    tcp_zm = zm_calc.compute_tcp_dvh(dvh, 30, hn)["tcp"]
    assert tcp_zm >= tcp_poisson - 0.001


def test_zm_approaches_poisson_for_large_n0():
    hn = SITE_PARAMS["HN"]
    p_calc = PoissonTCPCalculator()
    zm_calc = ZMTCPCalculator(dead_fraction=0.85)
    dvh = make_uniform_dvh(30.0)
    tcp_p = p_calc.compute_tcp_dvh(dvh, 15, hn)["tcp"]
    tcp_zm = zm_calc.compute_tcp_dvh(dvh, 15, hn)["tcp"]
    assert tcp_zm >= tcp_p


def test_zm_p0_limits():
    calc = ZMTCPCalculator(dead_fraction=0.85, t_obs_days=730)
    b = np.log(2) / 4.0
    mu = b * 0.85
    p0_short = calc._p0_single_cell(30.0, b, mu)
    p0_long = calc._p0_single_cell(730.0, b, mu)
    p0_inf = mu / b
    assert 0 < p0_short < p0_long <= p0_inf + 1e-6


# Group 4 — gEUD-TCP
def test_geud_uniform_dvh_equals_dose():
    dvh = make_uniform_dvh(60.0)
    for a in [-13.0, -10.0, -5.0, 1.0, 5.0]:
        geud = compute_geud(dvh, a)
        assert abs(geud - 60.0) < 0.01, f"gEUD should be 60 for uniform DVH at a={a}"


def test_geud_tcp_at_tcd50():
    tcp = geud_tcp_niemierko(60.0, 60.0, 2.0)
    assert abs(tcp - 0.5) < 1e-9


def test_geud_tcp_monotone():
    tcps = [geud_tcp_niemierko(g, 60.0, 2.0) for g in [40, 50, 60, 70, 80]]
    assert tcps == sorted(tcps)


def test_geud_cold_spot_sensitivity():
    dvh = pd.DataFrame({"dose_gy": [30.0, 60.0], "volume_frac": [0.1, 0.9]})
    dmean = 0.1 * 30 + 0.9 * 60
    geud = compute_geud(dvh, a=-10.0)
    assert geud < dmean
    assert geud > 29.0


def test_geud_a1_equals_dmean():
    dvh = make_ramp_dvh(40.0, 80.0, 100)
    dmean = (dvh["dose_gy"] * dvh["volume_frac"]).sum()
    geud = compute_geud(dvh, a=1.0)
    assert abs(geud - dmean) < 0.5


# Group 5 — Logistic TCP
def test_logistic_tcp_at_d50():
    tcp = logistic_tcp(60.0, D50_gy=60.0, k=2.0)
    assert abs(tcp - 0.5) < 1e-9


def test_logistic_tcp_monotone():
    tcps = [logistic_tcp(d, 60.0, 2.0) for d in [40, 50, 60, 70, 80]]
    assert tcps == sorted(tcps)


def test_logistic_tcp_asymptotes():
    assert logistic_tcp(0.001, 60.0, 2.0) < 0.01
    assert logistic_tcp(1000.0, 60.0, 2.0) > 0.999


# Group 6 — TCPCalculator integration
@pytest.fixture
def mock_dvh_result():
    from types import SimpleNamespace

    dvh_df = make_uniform_dvh(60.0)
    from dicompylercore.dvh import DVH

    counts = np.full(1, 1.0)
    bins = np.array([59.5, 60.5])
    dvh_obj = DVH(
        counts=counts,
        bins=bins,
        dvh_type="differential",
        dose_units="Gy",
        volume_units="cm3",
    )
    return SimpleNamespace(
        canonical_name="GTV",
        dvh_object=dvh_obj,
        dmean_gy=60.0,
        quality_flag="OK",
    )


@pytest.fixture
def mock_plan_meta():
    return {
        "prescription_dose_gy": 60.0,
        "n_fractions": 30,
        "dose_per_fraction_gy": 2.0,
        "plan_label": "TEST",
        "beam_type": "IMRT",
    }


def test_calculator_returns_all_models(mock_dvh_result, mock_plan_meta):
    result = TCPCalculator().compute_all(
        mock_dvh_result, mock_plan_meta, SITE_PARAMS["HN"]
    )
    for key in ["TCP_Poisson", "TCP_ZM", "TCP_gEUD", "TCP_Logistic"]:
        assert key in result
        assert 0.0 <= result[key] <= 1.0 or np.isnan(result[key])


def test_calculator_mean_range(mock_dvh_result, mock_plan_meta):
    result = TCPCalculator().compute_all(
        mock_dvh_result, mock_plan_meta, SITE_PARAMS["HN"]
    )
    valid = [
        float(v)
        for k, v in result.items()
        if k.startswith("TCP_")
        and k not in ("TCP_mean", "TCP_range")
        and isinstance(v, (int, float))
        and not np.isnan(v)
    ]
    assert valid
    assert abs(result["TCP_mean"] - np.mean(valid)) < 1e-6
    assert abs(result["TCP_range"] - (max(valid) - min(valid))) < 1e-6


def test_lq_caution_flag_set_for_sbrt(mock_dvh_result):
    plan_meta = {
        "dose_per_fraction_gy": 18.0,
        "n_fractions": 3,
        "prescription_dose_gy": 54.0,
    }
    dvh = make_sbrt_dvh()
    from types import SimpleNamespace

    res = SimpleNamespace(
        canonical_name="GTV",
        dvh_object=None,
        dmean_gy=54.0,
        quality_flag="OK",
    )
    from radiobiology import dvh_object_to_dataframe

    res.dvh_object = None
    frame = dvh
    from dicompylercore.dvh import DVH

    counts = np.array([1.0])
    bins = np.array([53.5, 54.5])
    res.dvh_object = DVH(
        counts=counts,
        bins=bins,
        dvh_type="differential",
        dose_units="Gy",
        volume_units="cm3",
    )
    result = TCPCalculator().compute_all(res, plan_meta, SITE_PARAMS["LUNG"])
    assert result["lq_caution"] is True
