"""Tests for the worked extension example (completion-spec D2).

Two things are being tested, and they are different claims:

1. **That the extension mechanism works.** A model defined entirely outside `engine/` reaches the
   engine's registry through `register_ntcp_model`, is returned by `iter_ntcp_models`, and is
   callable through the protocol the engine declares. If this suite passes, "anyone may extend" is
   demonstrated rather than asserted.

2. **That the added model is correct**, by the same standard as the engine's own 22 analytic
   positive controls: against dose-response identities that hold *by construction* in the published
   formalism, never against a previously observed output of this code. A test that locks in current
   behaviour would prove the extension runs, not that it is right.

Reference: Niemierko A. Med Phys 1999;26:1100 (gEUD); Gay HA, Niemierko A. Phys Med
2007;23:115-125 (gEUD-logistic NTCP).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples" / "extensions"))

from niemierko_logistic_ntcp import (  # noqa: E402
    NiemierkoLogisticNTCP,
    generalised_eud,
    install,
    niemierko_logistic_ntcp,
)

from radiobiology.model_registry import (  # noqa: E402
    clear_registries,
    iter_ntcp_models,
)

pytestmark = pytest.mark.unit


def uniform_dvh(dose_gy: float, n_bins: int = 100) -> pd.DataFrame:
    return pd.DataFrame({"dose_gy": [dose_gy] * n_bins,
                         "volume_frac": [1.0 / n_bins] * n_bins})


# ------------------------------------------------------------------ 1. the mechanism
def test_extension_reaches_the_engine_registry():
    """The whole point of D2: an out-of-engine model becomes visible to the engine."""
    clear_registries()
    assert "niemierko_logistic" not in iter_ntcp_models()
    model = install()
    reg = iter_ntcp_models()
    assert "niemierko_logistic" in reg
    assert reg["niemierko_logistic"] is model
    clear_registries()


def test_extension_satisfies_the_declared_protocol():
    """Structural typing only - the class has no engine base class in its MRO."""
    model = NiemierkoLogisticNTCP()
    assert callable(model.compute_ntcp_dvh)
    assert [c.__name__ for c in type(model).__mro__] == ["NiemierkoLogisticNTCP", "object"]
    out = model.compute_ntcp_dvh(uniform_dvh(30.0), {"TD50_gy": 30.0, "gamma50": 2.0, "a": 1.0})
    assert set(out) >= {"ntcp", "geud_gy", "model"}


def test_registration_is_idempotent():
    clear_registries()
    install()
    install()
    assert len(iter_ntcp_models()) == 1
    clear_registries()


# ------------------------------------------------------------------ 2. analytic controls
@pytest.mark.parametrize("td50", [26.0, 28.4, 39.9, 46.0, 76.0])
@pytest.mark.parametrize("gamma50", [0.5, 1.0, 2.0, 4.0])
def test_ntcp_is_exactly_half_at_td50(td50, gamma50):
    """NTCP(gEUD = TD50) = 0.5 identically, for every TD50 and every gamma50."""
    assert niemierko_logistic_ntcp(td50, td50, gamma50) == pytest.approx(0.5, abs=1e-12)


@pytest.mark.parametrize("gamma50", [0.5, 2.0, 4.0])
def test_ntcp_monotone_in_dose(gamma50):
    vals = [niemierko_logistic_ntcp(d, 40.0, gamma50) for d in np.linspace(5.0, 120.0, 60)]
    assert all(b > a for a, b in zip(vals, vals[1:], strict=False))
    assert vals[0] < 0.5 < vals[-1]


@pytest.mark.parametrize("gamma50", [1.0, 2.0, 3.5])
def test_gamma50_is_the_normalised_slope_at_td50(gamma50):
    """d NTCP / d(ln gEUD) = gamma50 at gEUD = TD50, which is what gamma50 means."""
    td50, h = 40.0, 1e-5
    hi = niemierko_logistic_ntcp(td50 * math.exp(h), td50, gamma50)
    lo = niemierko_logistic_ntcp(td50 * math.exp(-h), td50, gamma50)
    assert (hi - lo) / (2 * h) == pytest.approx(gamma50, rel=1e-4)


def test_ntcp_is_non_degenerate_across_a_realistic_oar_dvh():
    """Guards the saturation failure mode that defect #30's control was built for."""
    rng = np.random.default_rng(0)
    out = []
    for mean in np.linspace(10.0, 70.0, 25):
        doses = np.clip(rng.normal(mean, 6.0, 200), 0.1, None)
        g = generalised_eud(doses, np.full(200, 1 / 200), a=2.0)
        out.append(niemierko_logistic_ntcp(g, 46.0, 2.0))
    assert min(out) < 0.05 and max(out) > 0.95
    assert len(set(np.round(out, 6))) > 20


@pytest.mark.parametrize("dose", [5.0, 23.7, 50.0, 90.0])
def test_geud_at_a_equals_one_is_the_mean_dose(dose):
    dvh = uniform_dvh(dose)
    assert generalised_eud(dvh["dose_gy"], dvh["volume_frac"], a=1.0) == pytest.approx(dose)


def test_geud_ordering_in_the_exponent():
    """For a non-uniform DVH, gEUD increases with a: serial organs see the hot spot."""
    doses = np.array([10.0, 20.0, 60.0, 80.0])
    v = np.full(4, 0.25)
    g = [generalised_eud(doses, v, a=a) for a in (1.0, 2.0, 5.0, 10.0)]
    assert all(b > a for a, b in zip(g, g[1:], strict=False))
    assert g[0] == pytest.approx(doses.mean())


# ------------------------------------------------------------------ 3. fails closed
@pytest.mark.parametrize("bad", [
    {"TD50_gy": 0.0, "gamma50": 2.0}, {"TD50_gy": 40.0, "gamma50": 0.0},
    {"TD50_gy": -40.0, "gamma50": 2.0}, {"TD50_gy": float("nan"), "gamma50": 2.0},
    {"TD50_gy": 40.0, "gamma50": float("nan")}, {},
])
def test_invalid_parameters_give_nan_not_a_number(bad):
    """A missing or impossible parameter must not produce a plausible NTCP."""
    out = NiemierkoLogisticNTCP().compute_ntcp_dvh(uniform_dvh(40.0), {**bad, "a": 1.0})
    assert math.isnan(out["ntcp"])


def test_missing_dvh_columns_are_refused_with_a_reason():
    out = NiemierkoLogisticNTCP().compute_ntcp_dvh(
        pd.DataFrame({"wrong": [1.0]}), {"TD50_gy": 40.0, "gamma50": 2.0})
    assert math.isnan(out["ntcp"])
    assert "dose_gy" in out.get("reason", "")


def test_output_states_that_no_fractionation_correction_was_applied():
    """The extension must not let a caller assume an EQD2 correction it does not do."""
    out = NiemierkoLogisticNTCP().compute_ntcp_dvh(
        uniform_dvh(40.0), {"TD50_gy": 40.0, "gamma50": 2.0, "a": 1.0}, n_fractions=35)
    assert out["fractionation_corrected"] is False
    assert out["n_fractions"] == 35


def test_zero_dose_bins_are_dropped_not_clamped():
    """A zero-dose bin with negative a is a pole; dropping it is the honest choice."""
    doses = np.array([0.0, 40.0, 40.0, 40.0])
    v = np.full(4, 0.25)
    assert generalised_eud(doses, v, a=1.0) == pytest.approx(40.0)
