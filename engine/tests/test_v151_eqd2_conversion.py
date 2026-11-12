"""Defect #63: the EQD2 conversion was skipped whenever the PLAN sat near 2 Gy per fraction.

The skipped transform was described in the code as "the identity". It is the identity only for a
bin that is itself at 2 Gy per fraction, and a DVH is not one dose. In a 70 Gy / 35 fraction plan
a bin at 35 Gy receives 1 Gy per fraction, which is 28 Gy EQD2 at alpha/beta = 3. The published
fits these parameters come from (Rancati larynx, Bakhshandeh thyroid) were made on EQD2 DVHs, so
the skip scored those organs on physical dose against EQD2 parameters.

Every test here fails on v1.5.0 and passes after the fix.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from radiobiology.bdvh import compute_eqd2_dvh
from radiobiology.geud_tcp import compute_geud


def _two_bin_dvh() -> pd.DataFrame:
    """Half the volume at 35 Gy, half at 70 Gy."""
    return pd.DataFrame({"dose_gy": [35.0, 70.0], "volume_frac": [0.5, 0.5]})


def test_the_two_bin_dvh_converts_to_28_and_70_gy_eqd2():
    """#63: a 35 Gy bin over 35 fractions is 1 Gy/fraction -> 28 Gy EQD2 at alpha/beta = 3.

    EQD2 = D * (d + ab) / (2 + ab) = 35 * (1 + 3) / (2 + 3) = 28.
    The 70 Gy bin is at 2 Gy/fraction, so it alone is unchanged: 70 * (2+3)/(2+3) = 70.
    """
    out = compute_eqd2_dvh(_two_bin_dvh(), n_fractions=35, alpha_beta_oar_gy=3.0)
    assert out["dose_gy"].tolist() == pytest.approx([28.0, 70.0])


def test_the_geud_of_the_converted_dvh_matches_the_converted_bins():
    """The gEUD the NTCP uses must be the gEUD of the DVH the NTCP used."""
    out = compute_eqd2_dvh(_two_bin_dvh(), n_fractions=35, alpha_beta_oar_gy=3.0)
    # a = 1 is the volume-weighted mean: (28 + 70) / 2 = 49.
    assert compute_geud(out, a=1.0) == pytest.approx(49.0)
    # The physical DVH would have given (35 + 70) / 2 = 52.5. The two are not the same number,
    # which is the whole point of #63.
    assert compute_geud(_two_bin_dvh(), a=1.0) == pytest.approx(52.5)


def test_two_gy_per_fraction_is_the_identity_only_for_a_bin_at_two_gy_per_fraction():
    """#63's premise, stated as a test.

    The plan is 70 Gy in 35 fractions -- exactly 2 Gy per fraction, the case v1.5.0 skipped. The
    bin at the prescription dose is indeed unchanged. Every bin below it is not.
    """
    dvh = pd.DataFrame({"dose_gy": [10.0, 35.0, 52.5, 70.0], "volume_frac": [0.25] * 4})
    out = compute_eqd2_dvh(dvh, n_fractions=35, alpha_beta_oar_gy=3.0)
    converted = out["dose_gy"].tolist()

    # The bin at the prescription: 2 Gy/fraction, unchanged.
    assert converted[3] == pytest.approx(70.0)
    # Every lower bin moves, and moves DOWN.
    for physical, eqd2 in zip(dvh["dose_gy"][:3], converted[:3]):
        assert eqd2 < physical, f"{physical} Gy should fall under EQD2, got {eqd2}"
    # The 35 Gy bin is the worked example from the register entry.
    assert converted[1] == pytest.approx(28.0)


def test_the_conversion_depends_on_alpha_beta():
    """A different alpha/beta gives a different EQD2, so the organ's value must be used."""
    dvh = pd.DataFrame({"dose_gy": [35.0], "volume_frac": [1.0]})
    at_3 = compute_eqd2_dvh(dvh, 35, 3.0)["dose_gy"].iloc[0]
    at_10 = compute_eqd2_dvh(dvh, 35, 10.0)["dose_gy"].iloc[0]
    assert at_3 == pytest.approx(28.0)
    assert at_10 == pytest.approx(35.0 * (1.0 + 10.0) / (2.0 + 10.0))
    assert at_3 != pytest.approx(at_10)


def test_zero_dose_bins_stay_zero():
    """A 0 Gy bin must not become negative or NaN under the transform."""
    dvh = pd.DataFrame({"dose_gy": [0.0, 35.0], "volume_frac": [0.5, 0.5]})
    out = compute_eqd2_dvh(dvh, 35, 3.0)
    assert out["dose_gy"].iloc[0] == 0.0
    assert math.isfinite(out["dose_gy"].iloc[1])


# --------------------------------------------------------------------------------------------
# The tests above exercise compute_eqd2_dvh, which was already correct in v1.5.0. The defect was
# in its CALLER, which decided not to call it. These are the ones that fail on v1.5.0.
# --------------------------------------------------------------------------------------------

def _run_one_organ(monkeypatch, dpf_plan: float, n_fractions: int) -> dict:
    """Drive NTCPCalculator.compute_all over a known two-bin DVH."""
    from config.site_ntcp_params import OrganNTCPParams
    from radiobiology import ntcp_calculator as mod

    frame = _two_bin_dvh()
    monkeypatch.setattr(mod, "dvh_object_to_dataframe", lambda _obj: frame.copy())

    class _DvhResult:
        dvh_object = object()
        canonical_name = "Larynx"

    params = OrganNTCPParams(
        canonical="Larynx",
        geud_a=1.0,
        alpha_beta_gy=3.0,
        lkb_loglogit={"TD50_gy": 50.0, "gamma50": 2.0},
    )
    meta = {"n_fractions": n_fractions, "dose_per_fraction_gy": dpf_plan}
    return mod.NTCPCalculator().compute_all(_DvhResult(), meta, params, "HN", mode="advanced")


def test_a_two_gy_per_fraction_plan_still_gets_the_eqd2_transform(monkeypatch):
    """#63: v1.5.0 skipped the transform here, because |2.0 - 2.0| <= 0.3.

    The plan is 70 Gy in 35 fractions. The DVH has a bin at 35 Gy, which is 1 Gy per fraction and
    must become 28 Gy EQD2. On v1.5.0 `bdvh_applied` is False and the gEUD is the physical 52.5.
    """
    row = _run_one_organ(monkeypatch, dpf_plan=2.0, n_fractions=35)
    assert row["bdvh_applied"] is True
    assert row["ntcp_dose_basis"] == "eqd2"
    # gEUD at a = 1 over the EQD2 bins (28, 70) = 49, not the physical (35, 70) = 52.5.
    assert row["gEUD_gy"] == pytest.approx(49.0)


def test_the_reported_dose_statistics_stay_physical(monkeypatch):
    """Only the NTCP input is converted. Dmean/Dmax keep their stated meaning."""
    row = _run_one_organ(monkeypatch, dpf_plan=2.0, n_fractions=35)
    assert row["Dmax_gy"] == pytest.approx(70.0)
    # Physical volume-weighted mean of (35, 70) = 52.5. The EQD2 mean would be 49.
    assert row["Dmean_gy"] == pytest.approx(52.5)


def test_the_row_records_the_basis_and_the_alpha_beta_used(monkeypatch):
    """A reader must be able to tell which dose the NTCP was computed on, and reproduce it."""
    row = _run_one_organ(monkeypatch, dpf_plan=2.0, n_fractions=35)
    assert row["ntcp_dose_basis"] == "eqd2"
    assert row["alpha_beta_gy_used"] == pytest.approx(3.0)
    assert row["n_fractions_plan"] == 35


def test_unknown_fractionation_still_refuses_the_transform(monkeypatch):
    """#4/#5 must survive #63: an unstated fractionation is still 'physical', not a guess."""
    row = _run_one_organ(monkeypatch, dpf_plan=None, n_fractions=1)
    assert row["bdvh_applied"] is False
    assert row["ntcp_dose_basis"] == "physical"
    assert math.isnan(row["alpha_beta_gy_used"])


def test_the_retired_basis_label_is_gone(monkeypatch):
    """'physical_2gy_equivalent' asserted that 2 Gy/fraction needs no conversion. That was #63."""
    for dpf in (2.0, 2.2, 1.8):
        row = _run_one_organ(monkeypatch, dpf_plan=dpf, n_fractions=35)
        assert row["ntcp_dose_basis"] != "physical_2gy_equivalent"
