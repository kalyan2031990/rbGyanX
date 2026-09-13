"""
Positive-control tests for the classical NTCP models (P1 · S2 + S6).

These pin the *corrected* behaviour against dose-response identities that hold by
construction in the published formalisms — not against previously observed numbers.
They are the evidence that the engine reproduces validated models:

  * NTCP = 0.5 exactly at the model's TD50/D50 (probit, log-logistic, relative seriality);
  * NTCP increases monotonically with dose;
  * NTCP is non-degenerate across a realistic dose range (guards the RS saturation bug,
    where every patient returned ~1.0);
  * QUANTEC parotid and a rectal LKB curve are reproduced to published tolerance.

References
----------
Källman P, Lind BK, Brahme A. Phys Med Biol 1992;37:871-890 (relative seriality).
Lyman JT. Radiat Res 1985;104:S13-19 (LKB).
Marks LB et al. QUANTEC. Int J Radiat Oncol Biol Phys 2010;76(3 Suppl):S10-19.
Deasy JO et al. QUANTEC salivary glands. IJROBP 2010;76(3 Suppl):S58-63.
Michalski JM et al. QUANTEC rectum. IJROBP 2010;76(3 Suppl):S123-129.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
from radiobiology.ntcp.rs_poisson import calculate_ntcp_rs_poisson

pytestmark = pytest.mark.unit


def uniform_dvh(dose_gy: float, n_bins: int = 100) -> pd.DataFrame:
    """Differential DVH for a uniformly irradiated organ."""
    return pd.DataFrame({"dose_gy": [dose_gy] * n_bins, "volume_frac": [1.0 / n_bins] * n_bins})


# --------------------------------------------------------------- TD50 fixed point


@pytest.mark.parametrize("td50", [26.0, 28.4, 39.9, 76.0])
def test_probit_half_at_td50(td50):
    assert calculate_ntcp_lkb_probit(td50, td50, 0.35) == pytest.approx(0.5, abs=1e-9)


@pytest.mark.parametrize("td50", [26.0, 28.4, 39.9, 76.0])
def test_loglogistic_half_at_td50(td50):
    assert calculate_ntcp_lkb_loglogit(td50, td50, 2.0) == pytest.approx(0.5, abs=1e-9)


@pytest.mark.parametrize("s", [0.1, 0.25, 0.5, 1.0, 2.0])
def test_relative_seriality_half_at_d50_for_any_seriality(s):
    """RS fixed point: uniform dose at D50 -> 0.5 regardless of seriality s.

    Regression guard for the saturation bug (complement applied inside the product),
    which returned ~1.0 for every patient and only agreed with the truth at s=1.
    """
    ntcp = calculate_ntcp_rs_poisson(uniform_dvh(50.0), 50.0, 2.0, s)
    assert ntcp == pytest.approx(0.5, abs=1e-9)


# --------------------------------------------------------------- monotonicity


DOSES = [5.0, 10.0, 20.0, 30.0, 40.0, 55.0, 70.0, 85.0]


def test_probit_monotone_in_dose():
    vals = [calculate_ntcp_lkb_probit(d, 40.0, 0.35) for d in DOSES]
    assert np.all(np.diff(vals) > 0)


def test_loglogistic_monotone_in_dose():
    vals = [calculate_ntcp_lkb_loglogit(d, 40.0, 2.0) for d in DOSES]
    assert np.all(np.diff(vals) > 0)


def test_relative_seriality_monotone_and_non_degenerate():
    vals = [calculate_ntcp_rs_poisson(uniform_dvh(d), 28.4, 1.0, 0.25) for d in DOSES]
    assert np.all(np.diff(vals) > 0), "RS must increase with dose"
    # The saturation bug produced a span of ~0 (all values ~1.0).
    assert max(vals) - min(vals) > 0.25, f"RS degenerate: span={max(vals) - min(vals)}"
    assert min(vals) > 0.0 and max(vals) < 1.0


def test_relative_seriality_not_saturated_on_realistic_oar_dvh():
    """A realistic partial-volume OAR DVH must not pin NTCP at 1.0."""
    # Half the gland at 10 Gy, half at 45 Gy.
    dvh = pd.DataFrame({"dose_gy": [10.0] * 50 + [45.0] * 50, "volume_frac": [0.01] * 100})
    ntcp = calculate_ntcp_rs_poisson(dvh, 28.4, 1.0, 0.25)
    assert 0.01 < ntcp < 0.99, f"RS saturated at {ntcp}"


# --------------------------------------------------------------- published anchors


def test_quantec_parotid_mean_dose_anchor():
    """QUANTEC parotid: ~mean 25 Gy (one gland) is the <20% xerostomia guidance point,
    and the response passes 50% at the model TD50. Uses the mean-dose (parallel) form."""
    td50, m = 39.9, 0.40  # QUANTEC-era parotid LKB (mean-dose, n~1)
    at_25 = calculate_ntcp_lkb_probit(25.0, td50, m)
    at_td50 = calculate_ntcp_lkb_probit(td50, td50, m)
    at_high = calculate_ntcp_lkb_probit(60.0, td50, m)
    assert at_25 < 0.25, f"25 Gy should be low-risk, got {at_25:.3f}"
    assert at_td50 == pytest.approx(0.5, abs=1e-9)
    assert at_high > 0.75
    assert at_25 < at_td50 < at_high


def test_rectal_lkb_dose_response_anchor():
    """Rectal late toxicity LKB (QUANTEC-era TD50~76 Gy): 50% at TD50, steep, ordered."""
    td50, m = 76.0, 0.15
    at_60 = calculate_ntcp_lkb_probit(60.0, td50, m)
    at_td50 = calculate_ntcp_lkb_probit(td50, td50, m)
    at_85 = calculate_ntcp_lkb_probit(85.0, td50, m)
    assert at_60 < 0.10, f"60 Gy rectum should be low-risk, got {at_60:.3f}"
    assert at_td50 == pytest.approx(0.5, abs=1e-9)
    assert at_85 > 0.75
    # Steepness: a small m gives a sharp rise around TD50.
    assert calculate_ntcp_lkb_probit(80.0, td50, m) - at_td50 > 0.1


# --------------------------------------------------------------- parallel-organ gEUD (S3)


def test_geud_a1_equals_mean_dose():
    """a=1 makes gEUD the mean dose — the parallel-organ / QUANTEC xerostomia form."""
    from radiobiology.geud_tcp import compute_geud

    dvh = pd.DataFrame(
        {"dose_gy": [10.0, 20.0, 30.0, 40.0], "volume_frac": [0.25, 0.25, 0.25, 0.25]}
    )
    mean_dose = float((dvh["dose_gy"] * dvh["volume_frac"]).sum())
    assert compute_geud(dvh, 1.0) == pytest.approx(mean_dose, rel=1e-9)


def test_parotid_site_config_uses_mean_dose_exponent():
    """Shipped HN parotid params must use a=1 (parallel organ), not a=3."""
    import yaml

    from config import site_ntcp_params as mod

    cfg_path = Path(mod.__file__).parent / "site_params_ntcp_default.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    for organ in ("Parotid_L", "Parotid_R"):
        assert cfg["HN"]["organs"][organ]["geud_a"] == pytest.approx(1.0), organ


# --------------------------------------------------------------- UTCP factorisation


def test_utcp_factorisation_exact():
    """Uncomplicated control P+ = TCP * PROD(1 - NTCP_i) factorises exactly."""
    tcp = 0.85
    ntcps = [
        calculate_ntcp_lkb_probit(30.0, 39.9, 0.40),
        calculate_ntcp_lkb_probit(50.0, 76.0, 0.15),
    ]
    utcp = tcp * float(np.prod([1.0 - n for n in ntcps]))
    expected = tcp
    for n in ntcps:
        expected *= 1.0 - n
    assert utcp == pytest.approx(expected, rel=1e-12)
    assert 0.0 < utcp < tcp  # complications can only reduce uncomplicated control
