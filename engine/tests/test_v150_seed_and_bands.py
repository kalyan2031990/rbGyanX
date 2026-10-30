"""Tier A defects #6 and #7 — the manifest's seed, and the coverage of a 'band'.

Each test fails on v1.4.0 (``ffd69ef``) and passes after the fix.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config.site_params import load_site_params
from rbgyanx_engine.run_config import RunConfig
from uncertainty.ntcp_mc import BAND_LEVEL, NTCPUncertaintyConfig, run_untcp
from uncertainty.parameter_mc import ParamUncertaintyConfig, run_parameter_mc


def _target_dvh() -> pd.DataFrame:
    doses = np.linspace(60.0, 72.0, 60)
    return pd.DataFrame({"dose_gy": doses, "volume_frac": np.full(60, 1.0 / 60)})


def _oar_dvh() -> pd.DataFrame:
    doses = np.linspace(0.0, 50.0, 60)
    return pd.DataFrame({"dose_gy": doses, "volume_frac": np.full(60, 1.0 / 60)})


# ------------------------------------------------------------------------ #6 the run's own seed


def test_defect_6_runconfig_carries_a_seed() -> None:
    """#6: RunnerConfig.seed was written to the manifest but RunConfig had no seed to carry it."""
    assert hasattr(RunConfig(), "seed")
    assert RunConfig(seed=7).seed == 7


def test_defect_6_the_pipeline_phase_accepts_and_uses_the_seed() -> None:
    """#6: apply_uncertainty_and_hypoxia dropped the seed and always built the config with 42."""
    import inspect

    from rbgyanx_engine.pipeline import (
        apply_ntcp_uncertainty,
        apply_uncertainty_and_hypoxia,
    )

    for fn in (apply_uncertainty_and_hypoxia, apply_ntcp_uncertainty):
        assert "seed" in inspect.signature(fn).parameters, fn.__name__


def test_defect_6_cohort_runner_hands_its_seed_to_the_engine() -> None:
    """The manifest's seed must be the one the run used, not a coincidence."""
    import inspect

    from rbgyanx_engine import cohort_runner

    src = inspect.getsource(cohort_runner)
    assert "seed=cfg.seed" in src


def test_defect_6_different_seeds_give_different_bands() -> None:
    sp = load_site_params("HN")
    dvh = _target_dvh()
    a = run_parameter_mc(dvh, 35, sp, "GTV", ParamUncertaintyConfig(n_samples=120, seed=1))
    b = run_parameter_mc(dvh, 35, sp, "GTV", ParamUncertaintyConfig(n_samples=120, seed=2))
    key = "TCP_Poisson_mc"
    assert a[key]["p5"] != b[key]["p5"] or a[key]["p95"] != b[key]["p95"]


def test_defect_6_the_same_seed_gives_identical_bands() -> None:
    sp = load_site_params("HN")
    dvh = _target_dvh()
    a = run_parameter_mc(dvh, 35, sp, "GTV", ParamUncertaintyConfig(n_samples=120, seed=5))
    b = run_parameter_mc(dvh, 35, sp, "GTV", ParamUncertaintyConfig(n_samples=120, seed=5))
    key = "TCP_Poisson_mc"
    assert a[key]["p5"] == pytest.approx(b[key]["p5"])
    assert a[key]["p95"] == pytest.approx(b[key]["p95"])


# ----------------------------------------------------------------------- #7 band_level on rows


def test_defect_7_band_level_is_declared_and_is_ninety_percent() -> None:
    """#7: p5-p95 is a 90% interval, which nothing on the row said."""
    assert BAND_LEVEL == 0.90


def test_defect_7_parameter_mc_rows_carry_the_band_level() -> None:
    sp = load_site_params("HN")
    out = run_parameter_mc(
        _target_dvh(), 35, sp, "GTV", ParamUncertaintyConfig(n_samples=80, seed=0)
    )
    aggregates = [v for v in out.values() if isinstance(v, dict) and "p5" in v]
    assert aggregates, out.keys()
    for agg in aggregates:
        assert agg["band_level"] == 0.90


def test_defect_7_untcp_rows_carry_the_band_level() -> None:
    from config.site_ntcp_params import load_site_ntcp_params

    site = load_site_ntcp_params("HN")
    organ_key, organ = next(iter(site.organs.items()))
    out = run_untcp(_oar_dvh(), organ, config=NTCPUncertaintyConfig(n_samples=80, seed=0))
    aggregates = [v for v in out.values() if isinstance(v, dict) and "p5" in v]
    assert aggregates, (organ_key, out.keys())
    for agg in aggregates:
        assert agg["band_level"] == 0.90


def test_defect_7_an_empty_aggregate_still_declares_its_level() -> None:
    """A NaN band is still a 90% band; the level must not vanish with the numbers."""
    from uncertainty.ntcp_mc import _agg

    assert _agg(np.array([np.nan, np.nan]))["band_level"] == 0.90
