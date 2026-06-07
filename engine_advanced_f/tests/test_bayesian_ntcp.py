import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.special import ndtr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine_advanced_f"))

from rbgyanx_advanced_f.bayesian.ntcp_bayesian import (
    fit_lkb_bayesian,
    load_posterior,
    propagate_ntcp_uncertainty_bayesian,
    save_posterior,
)


def _synthetic_cohort(n: int = 40, seed: int = 7):
    rng = np.random.default_rng(seed)
    td50, m = 30.0, 0.2
    geud = rng.uniform(15, 55, size=n)
    p = ndtr((geud - td50) / (m * td50))
    y = (rng.random(n) < p).astype(float)
    return geud, y


def test_fit_lkb_bayesian_emulation():
    geud, y = _synthetic_cohort(45)
    post = fit_lkb_bayesian(geud, y, "Parotid", prefer_pymc=False)
    assert post.method == "bootstrap_emulation"
    assert len(post.td50_samples) >= 100
    assert 15 < post.td50_mean < 60
    assert post.n_patients == 45


def test_propagate_and_save_load(tmp_path):
    geud, y = _synthetic_cohort(35)
    post = fit_lkb_bayesian(geud, y, "lung", prefer_pymc=False)
    unc = propagate_ntcp_uncertainty_bayesian(40.0, post)
    assert 0 <= unc["ntcp_mean"] <= 1
    assert unc["ntcp_ci_lower"] <= unc["ntcp_ci_upper"]
    path = save_posterior(post, tmp_path / "lung.npz")
    loaded = load_posterior(path)
    assert loaded is not None
    assert loaded.organ == "lung"
    unc2 = propagate_ntcp_uncertainty_bayesian(40.0, loaded)
    assert abs(unc2["ntcp_mean"] - unc["ntcp_mean"]) < 0.05
