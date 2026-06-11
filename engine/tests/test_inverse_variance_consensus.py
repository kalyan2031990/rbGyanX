"""Tests for inverse-variance consensus (uTCP / uNTCP)."""

from __future__ import annotations

import math

import pytest

from uncertainty.inverse_variance_consensus import inverse_variance_consensus


def test_agreeing_models_variance_near_min():
    est = [0.5, 0.5, 0.5, 0.5]
    var = [0.01, 0.02, 0.015, 0.012]
    out = inverse_variance_consensus(est, var)
    assert abs(out["mean"] - 0.5) < 1e-9
    assert out["tau_squared"] < 1e-12
    assert out["variance"] <= min(var) + 1e-6


def test_diverging_models_tau_widens_interval():
    est = [0.2, 0.5, 0.8, 0.6]
    var = [0.01, 0.01, 0.01, 0.01]
    agree = inverse_variance_consensus([0.5, 0.5, 0.5, 0.5], var)
    diverge = inverse_variance_consensus(est, var)
    assert diverge["tau_squared"] > agree["tau_squared"]
    assert diverge["variance"] > agree["variance"]
