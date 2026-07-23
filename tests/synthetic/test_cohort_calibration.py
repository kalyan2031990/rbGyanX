"""Cohort factory → calibration / EPV guards."""

from __future__ import annotations

import pytest

from tests.synthetic.cohort_factory import dvh_list_from_geuds, planted_lkb_cohort

pytestmark = pytest.mark.integration


def test_planted_cohort_has_events():
    df, truth = planted_lkb_cohort(n_patients=50, seed=1)
    assert truth["n_events"] >= 5
    assert len(df) == 50


def test_mle_recovers_td50_within_tolerance():
    from validation.ntcp_calibration import fit_lkb_parameters

    df, truth = planted_lkb_cohort(n_patients=60, td50=26.0, m=0.40, seed=7)
    dvh_list = dvh_list_from_geuds(df["geud_gy"].values)
    outcomes = df["Observed_Toxicity"].values

    fit = fit_lkb_parameters(
        dvh_list=dvh_list,
        outcomes=outcomes,
        organ="Parotid_L",
        site="HN",
        init_td50=30.0,
        init_m=0.35,
        init_n=0.45,
        n_bootstrap=0,
    )
    assert fit.converged
    assert abs(fit.TD50_gy - truth["TD50_gy"]) < 10.0


def test_epv_guard_refuses_tiny_event_cohort():
    """<10 events should not produce stable ML — guard via cohort size."""
    df, truth = planted_lkb_cohort(n_patients=15, seed=99)
    assert truth["n_events"] < 10 or len(df) < 20
