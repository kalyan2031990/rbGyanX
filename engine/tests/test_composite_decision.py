"""Therapeutic index, window, P+, and ΔNTCP tests."""

from __future__ import annotations

import math

from radiobiology.composite_decision import (
    compute_utcp_p_plus,
    delta_ntcp,
    therapeutic_index,
    therapeutic_window,
)


def test_therapeutic_index_gt_one_for_separated_doses():
    ti = therapeutic_index(td50_gy=50.0, tcd50_gy=30.0)
    assert ti > 1.0


def test_therapeutic_window_empty_when_no_dose_satisfies_both():
    doses = [10.0, 20.0, 30.0, 40.0, 50.0]
    tcp = [0.1, 0.2, 0.3, 0.4, 0.45]
    ntcp = [0.5, 0.5, 0.5, 0.5, 0.5]
    w = therapeutic_window(doses, tcp, ntcp, tau_t=0.5, tau_n=0.1)
    assert w["empty"]


def test_utcp_p_plus_bounded_by_utcp():
    p_plus = compute_utcp_p_plus(0.8, {"Parotid": 0.2, "Cord": 0.1})
    assert p_plus <= 0.8
    assert math.isfinite(p_plus)


def test_delta_ntcp_flags_degradation():
    d = delta_ntcp({"Parotid": 0.1}, {"Parotid": 0.2}, threshold=0.05)
    assert d["per_oar"]["Parotid"]["degradation_flag"]
    assert d["any_degradation"]
