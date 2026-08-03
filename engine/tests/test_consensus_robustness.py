"""Permanent positive control for the consensus combiner (Analysis B, B12).

The engine default consensus combiner MUST be robust to a single confidently
mis-specified member: a model that is far from its peers but quotes a very narrow
uncertainty band must NOT be allowed to dominate the consensus. Inverse-variance
weighting fails this (weights ~ 1/sigma**2, so a narrow band buys unbounded
weight); the default median combiner passes it. These tests lock that guarantee in
place so a future refactor cannot silently reinstate the fragile default.

See ``analysis/preregistration_B.md`` (B4) and ``docs/CONSENSUS_B_RESULTS.md``.
"""

from __future__ import annotations

import math

import pytest

from uncertainty.inverse_variance_consensus import (
    DEFAULT_METHOD,
    combine_consensus,
    disagreement_penalty_consensus,
    inverse_variance_consensus,
    robust_median_consensus,
)


def test_default_method_is_robust_median():
    """The engine default combiner is the robust median, not inverse variance."""
    assert DEFAULT_METHOD == "median"
    out = combine_consensus([0.1, 0.2, 0.3], [0.01, 0.01, 0.01])
    assert out["method"] == "median"
    assert out["mean"] == pytest.approx(0.2)


def test_confident_outlier_does_not_dominate_default():
    """POSITIVE CONTROL — a confidently-wrong member must not capture the default
    consensus. Two honest members agree near 0.20; a third is far off (0.90) but
    quotes a band ~30x narrower. The default (median) must stay with the honest
    pair; inverse-variance must be dragged toward the outlier (proving the
    pathology is real and that this test discriminates)."""
    est = [0.20, 0.24, 0.90]
    var = [0.02, 0.02, 0.02 / 900.0]  # outlier band ~30x narrower -> ~900x weight

    default = combine_consensus(est, var)  # method defaults to median
    ivw = combine_consensus(est, var, method="inverse_variance")

    # Default consensus is NOT dragged to the confident outlier.
    assert default["mean"] == pytest.approx(0.24)  # median of the three
    assert abs(default["mean"] - 0.90) > 0.5
    assert default["mean"] <= 0.30

    # Inverse-variance IS captured by the confident outlier (the failure we guard
    # against). If this ever stops holding the positive control is meaningless.
    assert ivw["mean"] > 0.80
    outlier_weight = ivw["weights"][2] / sum(ivw["weights"])
    assert outlier_weight > 0.95


def test_disagreement_penalty_reins_in_outlier():
    """The disagreement-penalised variant must sit between naive IVW and the
    median: still influenced, but no longer dominated by the confident outlier."""
    est = [0.20, 0.24, 0.90]
    var = [0.02, 0.02, 0.02 / 900.0]
    ivw = combine_consensus(est, var, method="inverse_variance")["mean"]
    pen = combine_consensus(est, var, method="disagreement")["mean"]
    assert pen < ivw  # penalty pulls it back from the outlier
    assert pen < 0.80  # and it is no longer dominated


def test_median_band_robust_to_confident_outlier():
    """The default band must not collapse just because one member is over-confident:
    the within-model term uses the *median* variance, not the minimum."""
    honest = [0.20, 0.24, 0.28]
    var_ok = [0.02, 0.02, 0.02]
    var_poison = [0.02, 0.02, 0.02 / 900.0]
    band_ok = robust_median_consensus(honest, var_ok)["within_model_variance"]
    band_poison = robust_median_consensus(honest, var_poison)["within_model_variance"]
    # Median within-model variance is unchanged by one shrunken member.
    assert band_poison == pytest.approx(band_ok)


def test_agreeing_models_all_methods_agree():
    """When members agree, every combiner returns the shared value (median, IVW and
    disagreement coincide) — do-no-harm on the well-specified case."""
    est = [0.5, 0.5, 0.5]
    var = [0.01, 0.02, 0.015]
    for method in ("median", "inverse_variance", "disagreement"):
        assert combine_consensus(est, var, method=method)["mean"] == pytest.approx(0.5)


def test_inverse_variance_backward_compatible_shape():
    """The historical ``inverse_variance_consensus`` entry point keeps its exact
    return shape (no surprise ``method`` key) so existing callers/tests are unbroken."""
    out = inverse_variance_consensus([0.2, 0.5, 0.8, 0.6], [0.01, 0.01, 0.01, 0.01])
    assert set(out) == {"mean", "variance", "within_model_variance", "tau_squared", "sd", "weights"}
    assert out["tau_squared"] > 0


def test_all_nan_inputs_return_nan_with_method():
    for method in ("median", "inverse_variance", "disagreement"):
        out = combine_consensus([math.nan, math.nan], [-1.0, 0.0], method=method)
        assert math.isnan(out["mean"])
        assert out["method"] == method


def test_unknown_method_raises():
    with pytest.raises(ValueError, match="unknown consensus method"):
        combine_consensus([0.5], [0.1], method="bananas")


def test_disagreement_and_median_helpers_carry_method_key():
    assert disagreement_penalty_consensus([0.1, 0.9], [0.01, 0.01])["method"] == "disagreement"
    assert robust_median_consensus([0.1, 0.9], [0.01, 0.01])["method"] == "median"
