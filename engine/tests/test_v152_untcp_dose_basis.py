"""Pinning tests for defect #69: the Monte Carlo NTCP bands must be on the dose the estimate was.

Synthetic inputs only: a two-bin DVH, a hand-built organ-parameter object, and the Monte Carlo
drawn with every coefficient of variation set to zero so the "band" is deterministic and must
land exactly on the point estimate.

Both tests fail at tag v1.5.1 (`641b37b`), where `apply_ntcp_uncertainty` read the physical
histogram while the point estimate came from the EQD2 one:

* with the fractionation known, the band mean must equal the **EQD2** point estimate and must
  differ from the NTCP of the physical histogram -- at the tag it equalled the physical one;
* with the fractionation unknown, the bands are on physical dose and the row must say so --
  at the tag no row said anything, because the column did not exist.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.site_ntcp_params import OrganNTCPParams  # noqa: E402
from radiobiology.ntcp_calculator import NTCPCalculator  # noqa: E402
from rbgyanx_engine import pipeline  # noqa: E402

# 20 and 40 Gy in 35 fractions is 0.571 and 1.143 Gy per fraction -- both well under 2 Gy, so
# EQD2 is clearly BELOW the physical dose and the two bases cannot be confused for each other.
BINS = [10.0, 30.0, 50.0]          # edges -> centres 20 and 40 Gy
COUNTS = [50.0, 50.0]
N_FRACTIONS = 35


class _DVHObject:
    dvh_type = "differential"
    dose_units = "Gy"
    counts = COUNTS
    bins = BINS

    @property
    def differential(self):
        return self


class _DVH:
    def __init__(self, canonical: str = "SpinalCord"):
        self.canonical_name = canonical
        self.raw_name = canonical
        self.roi_number = 3
        self.total_volume_cc = 100.0
        self.extraction_mode = "synthetic"
        self.quality_flag = "OK"
        self.dvh_object = _DVHObject()


def _organ() -> OrganNTCPParams:
    """One sourced organ, all three models populated, so every band has something to draw."""
    sourced = {"illustrative": False, "source": "synthetic test fixture"}
    return OrganNTCPParams(
        canonical="SpinalCord",
        geud_a=10.0,
        alpha_beta_gy=3.0,
        lkb_loglogit={"TD50_gy": 50.0, "gamma50": 2.0},
        lkb_probit={"TD50_gy": 50.0, "m": 0.2, "n": 0.1},
        rs={"D50_gy": 50.0, "gamma": 2.0, "s": 1.0},
        provenance={k: dict(sourced) for k in
                    ("LKB_loglogit", "LKB_probit", "RS", "lkb_loglogit", "lkb_probit", "rs")},
        illustrative=False,
    )


@dataclass
class _Site:
    organs: dict


@pytest.fixture()
def deterministic_bands(monkeypatch):
    """Make the Monte Carlo deterministic: every CV zero, so each draw is the nominal parameter.

    `_truncated_normal` returns `np.full(n, mean)` when the standard deviation is zero, so the
    band collapses onto the value the nominal parameters give for whichever histogram was passed.
    That is what makes this a test of the histogram rather than of the sampler.
    """
    from uncertainty import ntcp_mc

    class _ZeroCV(ntcp_mc.NTCPUncertaintyConfig):
        def __init__(self, **kw):
            kw.update(TD50_cv=0.0, m_cv=0.0, n_cv=0.0, gamma50_cv=0.0,
                      D50_rs_cv=0.0, gamma_rs_cv=0.0, s_rs_cv=0.0)
            super().__init__(**kw)

    monkeypatch.setattr(ntcp_mc, "NTCPUncertaintyConfig", _ZeroCV)
    return _ZeroCV


def _row(n_fractions: int | None) -> dict:
    """One NTCP row, with the fractionation known or not."""
    meta: dict = {"n_fractions": n_fractions or 0}
    if n_fractions:
        meta["dose_per_fraction_gy"] = 70.0 / n_fractions
    return NTCPCalculator().compute_all(_DVH(), meta, _organ(), site_key="HN", mode="advanced")


def _bands(row: dict, monkeypatch, organ: OrganNTCPParams) -> dict:
    monkeypatch.setattr(pipeline, "load_site_ntcp_params",
                        lambda *a, **k: _Site(organs={"SpinalCord": organ}))
    rows = [row]
    pipeline.apply_ntcp_uncertainty(rows, "HN", None, n_mc=8, seed=7)
    return rows[0]


def test_defect_69_with_known_fractionation_the_band_sits_on_the_eqd2_estimate(
    deterministic_bands, monkeypatch
):
    """#69: the band must describe the number printed beside it."""
    organ = _organ()
    row = _row(N_FRACTIONS)
    assert row["ntcp_dose_basis"] == "eqd2", "the fixture must exercise the EQD2 path"
    point = float(row["NTCP_LKB_probit"])
    assert math.isfinite(point)

    out = _bands(row, monkeypatch, organ)
    band_mean = float(out["uNTCP_LKB_probit"]["mean"])
    assert band_mean == pytest.approx(point, rel=1e-9, abs=1e-12), (
        "the deterministic band mean is not the EQD2 point estimate, so the band was computed "
        "from a different histogram"
    )
    assert out["uNTCP_dose_basis"] == "eqd2"


def test_defect_69_the_band_is_not_the_physical_dose_ntcp(deterministic_bands, monkeypatch):
    """The two bases must be far enough apart for the test above to mean something."""
    organ = _organ()
    row = _row(N_FRACTIONS)
    physical = row["_dvh_df"]
    eqd2 = row["_dvh_df_ntcp"]
    assert float(eqd2["dose_gy"].max()) < float(physical["dose_gy"].max()), (
        "EQD2 should be below physical dose for this fixture"
    )

    from uncertainty.ntcp_mc import run_untcp

    cfg = deterministic_bands(n_samples=8, seed=7)
    on_physical = float(run_untcp(physical, organ, config=cfg)["uNTCP_LKB_probit"]["mean"])
    out = _bands(row, monkeypatch, organ)
    band_mean = float(out["uNTCP_LKB_probit"]["mean"])
    assert band_mean != on_physical, (
        "the band equals the physical-dose NTCP, which is what #69 was"
    )


def test_defect_69_with_unknown_fractionation_the_bands_are_physical_and_say_so(
    deterministic_bands, monkeypatch
):
    """No fractionation means no EQD2 conversion: the bands are on physical dose, recorded."""
    organ = _organ()
    row = _row(None)
    assert row["ntcp_dose_basis"] == "physical"
    point = float(row["NTCP_LKB_probit"])

    out = _bands(row, monkeypatch, organ)
    assert out["uNTCP_dose_basis"] == "physical"
    assert float(out["uNTCP_LKB_probit"]["mean"]) == pytest.approx(point, rel=1e-9, abs=1e-12)


def test_defect_69_every_model_band_follows_the_same_histogram(deterministic_bands, monkeypatch):
    """All three bands, not just the probit one that was easiest to check."""
    organ = _organ()
    row = _row(N_FRACTIONS)
    out = _bands(row, monkeypatch, organ)
    for model in ("LKB_probit", "LKB_loglogit", "RS"):
        point = float(out[f"NTCP_{model}"])
        band = float(out[f"uNTCP_{model}"]["mean"])
        assert math.isfinite(point) and math.isfinite(band), model
        assert band == pytest.approx(point, rel=1e-9, abs=1e-12), model
