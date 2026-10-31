"""Tier A defects #45, #36 and #35 — gEUD zero-dose bins and the EPV guard.

Each test here fails on v1.4.0 (``ffd69ef``) and passes after the fix.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from radiobiology.geud_tcp import (
    GEUD_ZERO_DOSE_NEG_A,
    compute_geud,
    compute_geud_with_reason,
)
from statistical_models.epv_guard import compute_epv, select_features_by_epv

# ------------------------------------------------------------------ #45 gEUD keeps 0-Gy bins


def _half_cold() -> pd.DataFrame:
    """Half the volume unirradiated, half at 70 Gy — the plan's own acceptance case."""
    return pd.DataFrame({"dose_gy": [0.0, 70.0], "volume_frac": [0.5, 0.5]})


def test_defect_45_positive_a_counts_the_unirradiated_half() -> None:
    """#45: ``mask = doses > 0`` dropped the cold half, so gEUD read 70 Gy, not 35."""
    assert compute_geud(_half_cold(), a=1.0) == pytest.approx(35.0)


def test_defect_45_a_equals_three() -> None:
    """#45: (0.5 * 70^3)^(1/3) = 55.56 Gy once the 0-Gy bin is kept."""
    assert compute_geud(_half_cold(), a=3.0) == pytest.approx(55.56, abs=0.01)


def test_defect_45_negative_a_is_zero_with_a_reason() -> None:
    """#45: the generalised mean with a < 0 goes to 0 when any occupied bin is at 0 Gy."""
    value, reason = compute_geud_with_reason(_half_cold(), a=-10.0)
    assert value == 0.0
    assert reason == GEUD_ZERO_DOSE_NEG_A


def test_defect_45_a1_equals_dmean_with_cold_bins() -> None:
    """gEUD at a=1 is the mean dose, which must include the unirradiated volume."""
    dvh = pd.DataFrame(
        {"dose_gy": [0.0, 10.0, 60.0], "volume_frac": [0.25, 0.25, 0.50]}
    )
    dmean = float((dvh["dose_gy"] * dvh["volume_frac"]).sum())
    assert compute_geud(dvh, a=1.0) == pytest.approx(dmean)
    assert dmean == pytest.approx(32.5)


def test_defect_45_reason_reaches_the_tcp_row() -> None:
    """#45: the flag has to survive as far as the written row, not stay inside the function."""
    from radiobiology.geud_tcp import GEUDTCPCalculator

    class _Params:
        geud_a = -10.0
        TCD50_gy = 60.0
        gamma50 = 2.0

    out = GEUDTCPCalculator().compute_tcp(_half_cold(), _Params())
    assert out["geud_reason"] == GEUD_ZERO_DOSE_NEG_A
    assert out["geud_gy"] == 0.0


def test_defect_45_keeps_refusing_what_is_genuinely_uncomputable() -> None:
    """Zero volume, a negative dose and a = 0 stay NaN; only the cold-bin case changed."""
    assert math.isnan(compute_geud(pd.DataFrame({"dose_gy": [], "volume_frac": []}), 1.0))
    assert math.isnan(
        compute_geud(pd.DataFrame({"dose_gy": [50.0], "volume_frac": [0.0]}), 1.0)
    )
    assert math.isnan(
        compute_geud(pd.DataFrame({"dose_gy": [-1.0, 50.0], "volume_frac": [0.5, 0.5]}), 1.0)
    )
    assert math.isnan(compute_geud(_half_cold(), 0.0))
    assert math.isnan(compute_geud(None, 1.0))


def test_defect_45_an_entirely_unirradiated_structure_is_zero_not_nan() -> None:
    """A structure that received no dose has gEUD 0 Gy; NaN said 'uncomputable', which is wrong."""
    dvh = pd.DataFrame({"dose_gy": [0.0, 0.0], "volume_frac": [0.5, 0.5]})
    assert compute_geud(dvh, a=1.0) == 0.0


# ------------------------------------------------------------------ #36 the EPV event label


def _cohort(n_events: int, n_total: int, event: int, other: int) -> np.ndarray:
    return np.array([event] * n_events + [other] * (n_total - n_events))


def test_defect_36_epv_is_the_same_under_inverted_labels() -> None:
    """#36: the guard hard-coded ``y == 0``, so inverting the coding changed the answer."""
    as_zero = _cohort(12, 100, event=0, other=1)
    as_one = _cohort(12, 100, event=1, other=0)
    a = compute_epv(as_zero, n_features=2, event_label=0)
    b = compute_epv(as_one, n_features=2, event_label=1)
    assert a.n_events == b.n_events == 12
    assert a.epv == b.epv == pytest.approx(6.0)
    assert not a.passes and not b.passes


def test_defect_36_the_old_hard_coded_count_would_have_been_wrong() -> None:
    """With 1 = event, counting zeros would have reported 88 events instead of 12."""
    y = _cohort(12, 100, event=1, other=0)
    assert compute_epv(y, n_features=2, event_label=1).n_events == 12
    assert int(np.sum(y == 0)) == 88  # what v1.4.0 counted


def test_defect_36_the_guard_raises_without_an_event_label() -> None:
    """#36: nothing may be inferred — omitting the label is an error, not a default."""
    y = _cohort(12, 100, event=1, other=0)
    with pytest.raises(TypeError):
        compute_epv(y, 2)  # type: ignore[call-arg]


def test_defect_36_a_label_that_does_not_occur_is_refused() -> None:
    y = _cohort(12, 100, event=1, other=0)
    with pytest.raises(ValueError, match="does not occur in y"):
        compute_epv(y, n_features=2, event_label=2)


def test_defect_36_a_non_binary_outcome_is_refused() -> None:
    y = np.array([0, 1, 2] * 10)
    with pytest.raises(ValueError, match="not binary"):
        compute_epv(y, n_features=1, event_label=1)


def test_defect_36_select_features_also_takes_the_label() -> None:
    y = _cohort(30, 100, event=1, other=0)
    selected, result = select_features_by_epv(
        ["a", "b", "c", "d"], y, event_label=1
    )
    assert len(selected) == 3
    assert result.passes
    assert result.event_label == 1
    with pytest.raises(TypeError):
        select_features_by_epv(["a"], y)  # type: ignore[call-arg]


# ------------------------------------------------------------------ #35 EPV is printed as 3 s.f.


def test_defect_35_small_epv_is_not_rounded_to_zero() -> None:
    """#35: ``{epv:.1f}`` printed 0.024 as '0.0', which reads as no events at all."""
    y = _cohort(12, 100, event=1, other=0)
    result = compute_epv(y, n_features=500, event_label=1)
    assert result.epv == pytest.approx(0.024)
    assert "EPV=0.024" in result.warning_message
    assert "EPV=0.0 " not in result.warning_message


def test_defect_35_safety_guard_report_uses_three_significant_figures() -> None:
    from validation.clinical_safety_guard import run_safety_checks

    report = run_safety_checks(
        "clinical_logistic", auc=0.70, calibration_slope=1.0, epv=0.024, n_patients=100
    )
    epv_messages = [c.message for c in report.checks if c.criterion == "EPV"]
    assert epv_messages, report
    assert "EPV=0.024" in epv_messages[0]
