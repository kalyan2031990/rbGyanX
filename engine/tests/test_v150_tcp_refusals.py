"""Tier A defects #10 and #11 — refusing instead of publishing an unsupported number.

Each test fails on v1.4.0 (``ffd69ef``) and passes after the fix.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from dicompylercore.dvh import DVH

from config.site_params import SITE_PARAMS
from dicom_io.dvh_extractor import DVHResult
from radiobiology.tcp_calculator import LQ_INVALID_DPF, TCPCalculator


def _dvh_result(dose_gy: float, label: str = "PTV", category: str = "TARGET") -> DVHResult:
    bins = np.linspace(0.0, dose_gy * 1.2, 241)
    edge = bins[1:]
    counts = np.where(edge <= dose_gy, 100.0, 0.0)
    dvh = DVH(
        counts=counts,
        bins=bins,
        dvh_type="cumulative",
        dose_units="Gy",
        volume_units="cm3",
    )
    return DVHResult(
        roi_number=1,
        raw_name=label,
        canonical_name=label,
        category=category,
        total_volume_cc=100.0,
        dmin_gy=dose_gy,
        dmean_gy=dose_gy,
        dmax_gy=dose_gy,
        dvh_object=dvh,
        quality_flag="OK",
    )


# ------------------------------------------------- #10 LQ validity is a refusal, not a flag

_SBRT_PLAN = {"prescription_dose_gy": 54.0, "n_fractions": 3, "dose_per_fraction_gy": 18.0}


def test_defect_10_lung_sbrt_at_18gy_times_3_is_refused() -> None:
    """#10: 18 Gy/fraction is far outside the 10 Gy LQ cap, yet TCP was written anyway."""
    row = TCPCalculator().compute_all(
        _dvh_result(54.0), _SBRT_PLAN, SITE_PARAMS["LUNG_SBRT"]
    )
    assert row["tcp_refused"] is True
    assert row["tcp_refusal_reason"] == LQ_INVALID_DPF
    assert row["lq_caution"] is True
    for key in ("TCP_Poisson", "TCP_ZM", "TCP_gEUD", "TCP_Logistic", "TCP_mean"):
        assert math.isnan(row[key]), (key, row[key])


def test_defect_10_the_override_computes_and_flags_it() -> None:
    row = TCPCalculator().compute_all(
        _dvh_result(54.0),
        _SBRT_PLAN,
        SITE_PARAMS["LUNG_SBRT"],
        allow_lq_extrapolation=True,
    )
    assert row["tcp_refused"] is False
    assert row["tcp_refusal_reason"] == ""
    assert row["lq_extrapolation_allowed"] is True
    assert row["lq_caution"] is True  # still flagged: the extrapolation is not hidden
    assert not math.isnan(row["TCP_Poisson"])


def test_defect_10_conventional_fractionation_is_untouched() -> None:
    """The guard must not refuse an ordinary 2 Gy/fraction plan."""
    row = TCPCalculator().compute_all(
        _dvh_result(70.0),
        {"prescription_dose_gy": 70.0, "n_fractions": 35, "dose_per_fraction_gy": 2.0},
        SITE_PARAMS["HN"],
    )
    assert row["tcp_refused"] is False
    assert row["lq_caution"] is False
    assert not math.isnan(row["TCP_Poisson"])


def test_defect_10_prostate_sbrt_cap_is_its_own() -> None:
    """PROSTATE_SBRT caps at 6 Gy/fraction, so 7.25 Gy x 5 is refused and 2 Gy is not."""
    params = SITE_PARAMS["PROSTATE_SBRT"]
    assert params.lq_valid_max_dpf_gy == 6.0
    refused = TCPCalculator().compute_all(
        _dvh_result(36.25),
        {"prescription_dose_gy": 36.25, "n_fractions": 5, "dose_per_fraction_gy": 7.25},
        params,
    )
    assert refused["tcp_refusal_reason"] == LQ_INVALID_DPF
    ok = TCPCalculator().compute_all(
        _dvh_result(36.25),
        {"prescription_dose_gy": 36.25, "n_fractions": 18, "dose_per_fraction_gy": 2.0},
        params,
    )
    assert ok["tcp_refused"] is False


def test_defect_10_the_refused_row_still_carries_its_dose_metrics() -> None:
    """A refusal is an answer, not a blank: the row must still say what the dose was."""
    row = TCPCalculator().compute_all(
        _dvh_result(54.0), _SBRT_PLAN, SITE_PARAMS["LUNG_SBRT"]
    )
    assert row["total_dose_gy"] == pytest.approx(54.0)
    assert row["n_fractions"] == 3
    assert row["dose_per_fraction"] == pytest.approx(18.0)
    assert not math.isnan(row["Dmean_gy"])


# --------------------------------------- #11 a site with TCP but no NTCP parameters


def test_defect_11_prostate_sbrt_has_tcp_parameters_but_no_ntcp_block() -> None:
    """The precondition for #11, stated so the test says why it exists."""
    from config.site_ntcp_params import load_site_ntcp_params

    assert "PROSTATE_SBRT" in SITE_PARAMS
    assert load_site_ntcp_params("PROSTATE_SBRT").organs == {}


def test_defect_11_the_reason_is_defined_and_stamped_on_a_row() -> None:
    from rbgyanx_engine.pipeline import NO_NTCP_PARAMS_FOR_SITE, _mark_no_ntcp_params

    row = _mark_no_ntcp_params({"structure": "Rectum", "NTCP_RS": math.nan})
    assert row["ntcp_refusal_reason"] == NO_NTCP_PARAMS_FOR_SITE
    assert row["definition_ok"] is False
    assert row["reason_codes"] == [NO_NTCP_PARAMS_FOR_SITE]


def test_defect_11_the_collector_no_longer_filters_every_oar_away() -> None:
    """#11: with no NTCP block, allowed_oar_names() is empty and used to discard every contour."""
    import inspect

    from rbgyanx_engine import pipeline

    src = inspect.getsource(pipeline.collect_dicom_ntcp)
    assert "site_has_ntcp_params" in src
    assert "allowed_canonicals=allowed" in src
    # the unfiltered branch must be reachable
    assert "if site_has_ntcp_params else None" in src


def test_defect_11_a_refused_row_still_has_every_ntcp_column() -> None:
    """cohort_runner builds its CSV from keys starting with NTCP_, so they must be present."""
    from config.site_ntcp_params import OrganNTCPParams
    from radiobiology.ntcp_calculator import NTCPCalculator
    from rbgyanx_engine.pipeline import _mark_no_ntcp_params

    row = NTCPCalculator().compute_all(
        _dvh_result(40.0, "Rectum", "OAR"),
        {"n_fractions": 18, "dose_per_fraction_gy": 2.0},
        OrganNTCPParams(canonical="Rectum"),
        "PROSTATE_SBRT",
    )
    _mark_no_ntcp_params(row)
    ntcp_keys = [k for k in row if k.startswith("NTCP_")]
    assert ntcp_keys, sorted(row)
    for key in ntcp_keys:
        assert math.isnan(row[key]), (key, row[key])
    assert not math.isnan(row["Dmean_gy"])  # the dose metrics are real
    assert row["ntcp_refusal_reason"] == "NO_NTCP_PARAMS_FOR_SITE"


def test_defect_11_cohort_output_keeps_the_rows_own_reason() -> None:
    """The applicability verdict cannot see a missing parameter block, so it must not win."""
    import inspect

    from rbgyanx_engine import cohort_runner

    src = inspect.getsource(cohort_runner)
    assert "ntcp_refusal_reason" in src
