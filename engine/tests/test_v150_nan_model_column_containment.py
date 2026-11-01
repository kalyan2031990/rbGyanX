"""A NaN model column must not shorten a composite, a ranking or a validation metric.

Four organs lost their `NTCP_LKB_loglogit` **value** in v1.5.0 — HN `Larynx`, HN `Mandible`,
BREAST `Thyroid` and `Esophagus` at every site — because an unsourced log-logistic block was
replaced by a published probit fit. The column still exists and is NaN for them.

That is correct as a *reported* value: the log-logistic model was not applied, and NaN says so.
The hazard is what happens downstream. A consumer that reads one fixed model column gets NaN for
part of its input, and then either refuses (correct), silently drops those rows (wrong), or
computes a metric on nothing (wrong). This module pins all three outcomes.

The regression these tests were written for was real and was introduced by the parameter change
itself: with the organs split between two model forms, **no single column could score the
head-and-neck OAR set**, so P+ refused outright at the one site the project reports most.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from config.site_ntcp_params import load_site_ntcp_params
from radiobiology.ntcp_row import NTCP_MODEL_ORDER, select_ntcp
from radiobiology.utcp import (
    UTCP_OAR_MAP,
    attach_utcp_to_tcp_results,
    compute_utcp,
    resolve_oar_map,
)

#: The organs whose log-logistic value is now NaN, and the site each is reached through.
LOGLOGIT_NOW_NAN = (
    ("HN", "Larynx"),
    ("HN", "Mandible"),
    ("BREAST", "Thyroid"),
    ("HN", "Esophagus"),
    ("LUNG", "Esophagus"),
    ("BREAST", "Esophagus"),
    ("LIVER", "Esophagus"),
)


# --------------------------------------------------------- the premise, stated as a test


@pytest.mark.parametrize("site, organ", LOGLOGIT_NOW_NAN)
def test_the_organ_has_no_loglogistic_block_any_more(site: str, organ: str) -> None:
    """These are the organs the rest of the module is about."""
    params = load_site_ntcp_params(site).organs[organ]
    assert params.lkb_loglogit is None, (site, organ)
    assert params.lkb_probit is not None, (site, organ)
    assert not params.illustrative, (site, organ)


def test_the_head_and_neck_oar_set_is_split_across_two_model_forms() -> None:
    """The condition that broke P+: neither column alone covers the set."""
    organs = load_site_ntcp_params("HN").organs
    oars = [e["oar"] for e in resolve_oar_map(UTCP_OAR_MAP["HN"])]
    with_loglogit = {o for o in oars if organs[o].lkb_loglogit}
    with_probit = {o for o in oars if organs[o].lkb_probit}
    assert with_loglogit and with_probit
    assert with_loglogit != set(oars), "a single column would have sufficed"
    assert with_probit != set(oars), "a single column would have sufficed"
    assert with_loglogit | with_probit == set(oars), "every OAR must be scoreable by some model"


# --------------------------------------------------------- selection reaches every model


def _split_rows() -> list[dict]:
    """HN OAR rows as the engine now writes them: each organ scored by its own model only."""
    organs = load_site_ntcp_params("HN").organs
    rows = []
    for oar in [e["oar"] for e in resolve_oar_map(UTCP_OAR_MAP["HN"])]:
        row = {"AnonPatientID": "P1", "structure": oar}
        row["NTCP_LKB_loglogit"] = 0.1 if organs[oar].lkb_loglogit else math.nan
        row["NTCP_LKB_probit"] = 0.1 if organs[oar].lkb_probit else math.nan
        rows.append(row)
    return rows


def test_select_ntcp_finds_the_value_whichever_model_produced_it() -> None:
    for row in _split_rows():
        value, model = select_ntcp(row)
        assert not math.isnan(value), row["structure"]
        assert model in NTCP_MODEL_ORDER, (row["structure"], model)


def test_select_ntcp_honours_the_preference_when_it_is_available() -> None:
    both = {"NTCP_LKB_loglogit": 0.2, "NTCP_LKB_probit": 0.3, "NTCP_RS": 0.4}
    assert select_ntcp(both, preferred="LKB_loglogit") == (0.2, "LKB_loglogit")
    assert select_ntcp(both, preferred="NTCP_RS") == (0.4, "RS")
    assert select_ntcp(both) == (0.3, "LKB_probit")  # the default order prefers the probit fit


def test_select_ntcp_falls_back_when_the_preference_is_nan() -> None:
    only_probit = {"NTCP_LKB_loglogit": math.nan, "NTCP_LKB_probit": 0.3}
    assert select_ntcp(only_probit, preferred="LKB_loglogit") == (0.3, "LKB_probit")


def test_select_ntcp_reports_nothing_rather_than_inventing_a_value() -> None:
    """An organ with no finite NTCP at all was not scored, and must say so."""
    value, model = select_ntcp({"NTCP_LKB_loglogit": math.nan, "NTCP_LKB_probit": math.nan})
    assert math.isnan(value)
    assert model == ""


# --------------------------------------------------------- P+ cannot be shortened


def test_p_plus_scores_every_oar_despite_the_nan_column() -> None:
    """The regression: reading one column reported four of the eight OARs missing."""
    result = compute_utcp({"AnonPatientID": "P1", "TCP_Poisson": 0.8}, _split_rows(), "HN")
    assert result.n_oars_missing == 0, result.missing_OAR_names
    assert result.n_oars_scored == 8
    assert result.reason == ""
    assert not math.isnan(result.UTCP)
    assert pytest.approx(0.8 * 0.9**8) == result.UTCP


@pytest.mark.parametrize("preferred", ["LKB_loglogit", "LKB_probit", "RS"])
def test_p_plus_is_the_same_whichever_model_is_preferred(preferred: str) -> None:
    """The preference may not decide whether P+ exists; only which model is tried first."""
    result = compute_utcp(
        {"AnonPatientID": "P1", "TCP_Poisson": 0.8},
        _split_rows(),
        "HN",
        ntcp_model=preferred,
    )
    assert result.n_oars_missing == 0
    assert pytest.approx(0.8 * 0.9**8) == result.UTCP


def test_p_plus_records_which_model_scored_each_oar() -> None:
    result = compute_utcp({"AnonPatientID": "P1", "TCP_Poisson": 0.8}, _split_rows(), "HN")
    assert len(result.scored_OAR_models) == len(result.scored_OAR_names)
    assert all(m for m in result.scored_OAR_models), result.scored_OAR_models
    assert set(result.scored_OAR_models) == {"LKB_loglogit", "LKB_probit"}


def test_a_mixed_model_product_is_flagged_not_hidden() -> None:
    """A P+ drawn from two model forms is a property of the number a reader must see."""
    mixed = compute_utcp({"AnonPatientID": "P1", "TCP_Poisson": 0.8}, _split_rows(), "HN")
    assert mixed.mixed_ntcp_models is True

    uniform_rows = [
        {"AnonPatientID": "P1", "structure": e["oar"], "NTCP_LKB_probit": 0.1}
        for e in resolve_oar_map(UTCP_OAR_MAP["HN"])
    ]
    single = compute_utcp({"AnonPatientID": "P1", "TCP_Poisson": 0.8}, uniform_rows, "HN")
    assert single.mixed_ntcp_models is False
    assert set(single.scored_OAR_models) == {"LKB_probit"}


def test_the_attached_row_carries_the_models_and_the_mixed_flag() -> None:
    tcp_rows = [{"AnonPatientID": "P1", "TCP_Poisson": 0.8}]
    attach_utcp_to_tcp_results(tcp_rows, _split_rows(), "HN")
    row = tcp_rows[0]
    assert row["UTCP_NTCP_models"] == "LKB_loglogit, LKB_probit"
    assert row["UTCP_mixed_NTCP_models"] is True
    assert not math.isnan(row["UTCP"])
    assert row["UTCP_OARs_missing"] == 0


def test_a_genuinely_unscored_oar_is_still_refused() -> None:
    """Containment must not become permissiveness: a missing organ still refuses P+."""
    rows = [r for r in _split_rows() if r["structure"] != "Larynx"]
    result = compute_utcp({"AnonPatientID": "P1", "TCP_Poisson": 0.8}, rows, "HN")
    assert math.isnan(result.UTCP)
    assert result.reason == "UTCP_INCOMPLETE_OAR_SET"
    assert result.missing_OAR_names == ["Larynx"]


def test_an_oar_whose_every_model_is_nan_is_refused_not_skipped() -> None:
    rows = _split_rows()
    for row in rows:
        if row["structure"] == "Mandible":
            row["NTCP_LKB_probit"] = math.nan
    result = compute_utcp({"AnonPatientID": "P1", "TCP_Poisson": 0.8}, rows, "HN")
    assert math.isnan(result.UTCP)
    assert "Mandible" in result.missing_OAR_names


# --------------------------------------------------------- a ranking cannot be shortened


def test_the_patient_summary_ranking_spans_every_model() -> None:
    """The PDF's "top OARs" read NTCP_LKB_loglogit first, so NaN rows dropped out silently."""
    import inspect

    from outputs import patient_summary_pdf

    src = inspect.getsource(patient_summary_pdf)
    assert "select_ntcp" in src, "the ranking must not read one fixed model column"


def test_a_ranking_over_split_rows_keeps_every_organ() -> None:
    """The behaviour the PDF now relies on, tested directly rather than through matplotlib."""
    rows = _split_rows()
    rows[0]["NTCP_LKB_probit"] = 0.9  # make one organ the clear top
    ranked = sorted(rows, key=lambda r: select_ntcp(r)[0], reverse=True)
    assert len(ranked) == len(rows), "no row may be dropped for want of a model column"
    assert ranked[0]["structure"] == rows[0]["structure"]
    assert all(not math.isnan(select_ntcp(r)[0]) for r in ranked)


# --------------------------------------------------------- a metric cannot be computed on NaN


def test_an_all_nan_prediction_column_is_skipped_by_the_validation_step() -> None:
    import inspect

    from rbgyanx_engine import engine

    src = inspect.getsource(engine)
    assert "np.isfinite(y_pred).any()" in src, (
        "validating an all-NaN prediction column would report a metric computed on nothing"
    )


def test_numpy_agrees_that_an_all_nan_column_carries_no_information() -> None:
    """The premise of the guard above, so it is not taken on trust."""
    assert not np.isfinite(np.array([math.nan, math.nan])).any()
    assert np.isfinite(np.array([math.nan, 0.3])).any()


# --------------------------------------------------------- the uncertainty consensus


def test_the_untcp_consensus_already_excludes_a_nan_model() -> None:
    """``run_untcp`` only contributes a model with a finite mean and a positive sd."""
    import inspect

    from uncertainty import ntcp_mc

    src = inspect.getsource(ntcp_mc.run_untcp)
    assert "math.isfinite(mean)" in src
    assert "math.isfinite(sd)" in src
