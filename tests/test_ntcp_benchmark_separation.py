"""
NTCP benchmark uses the engine's real models, and TCP/NTCP paths stay separate
(P1 · S1 + S5).

Guards the defect where an NTCP arm's "classical" tier was a logistic fitted to the data
(a proxy that cannot validate the tool) and where the TCP-specific ``1 - TCP`` predictor
could reach an NTCP arm.
"""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest

from validation import ntcp_benchmark as nb
from validation.ntcp_benchmark import (
    classical_ntcp,
    fit_ntcp_mle,
    run_ntcp_benchmark,
)

pytestmark = pytest.mark.unit


def _cohort(n: int = 80, seed: int = 0) -> pd.DataFrame:
    """Synthetic OAR cohort with a TRUE positive dose->toxicity association."""
    rng = np.random.default_rng(seed)
    dose = rng.uniform(10, 60, n)
    p = 1.0 / (1.0 + np.exp(-(dose - 35.0) / 6.0))  # higher dose -> more toxicity
    y = (rng.uniform(size=n) < p).astype(int)
    return pd.DataFrame(
        {
            "patient_id": [f"P{i:03d}" for i in range(n)],
            "centre": rng.choice(["a", "b", "c", "d"], size=n),
            "OAR_gEUD_gy": dose,
            "OAR_Dmean_gy": dose - 1.0,
            "OAR_dose_std_gy": rng.uniform(1, 5, n),
            "toxicity": y,
        }
    )


# --------------------------------------------------------------- classical = engine model


def test_classical_ntcp_is_the_engine_probit():
    from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit

    dose = [20.0, 40.0, 60.0]
    got = classical_ntcp("lkb_probit", {"TD50_gy": 40.0, "m": 0.3}, dose_metric=dose)
    want = [calculate_ntcp_lkb_probit(d, 40.0, 0.3) for d in dose]
    np.testing.assert_allclose(got, want, rtol=1e-9)


def test_classical_ntcp_is_the_engine_rs():
    from radiobiology.ntcp.rs_poisson import calculate_ntcp_rs_poisson

    dvh = pd.DataFrame({"dose_gy": [10.0] * 50 + [45.0] * 50, "volume_frac": [0.01] * 100})
    got = classical_ntcp("rs_poisson", {"D50_gy": 28.4, "gamma": 1.0, "s": 0.25}, dvhs=[dvh])
    want = calculate_ntcp_rs_poisson(dvh, 28.4, 1.0, 0.25)
    assert got[0] == pytest.approx(want, rel=1e-9)


def test_classical_polarity_is_direct():
    """Higher NTCP must mean higher toxicity probability — no 1-TCP inversion."""
    p = classical_ntcp("lkb_probit", {"TD50_gy": 40.0, "m": 0.3}, dose_metric=[10.0, 40.0, 70.0])
    assert p[0] < p[1] < p[2]


def test_unknown_model_rejected():
    with pytest.raises(ValueError, match="unknown NTCP model"):
        classical_ntcp("logistic_proxy", {}, dose_metric=[1.0])


def test_scalar_model_requires_dose_metric():
    with pytest.raises(ValueError, match="requires dose_metric"):
        classical_ntcp("lkb_probit", {"TD50_gy": 40.0, "m": 0.3})


# --------------------------------------------------------------- T2 MLE refit


def test_mle_refit_recovers_the_same_model_family():
    df = _cohort(200, seed=3)
    fit = fit_ntcp_mle("lkb_probit", df["OAR_gEUD_gy"], df["toxicity"])
    assert set(fit) >= {"TD50_gy", "m"}
    assert 15.0 < fit["TD50_gy"] < 60.0, fit  # near the true midpoint (~35 Gy)
    assert fit["m"] > 0
    # Refit remains a monotone dose-response.
    p = classical_ntcp(
        "lkb_probit", {"TD50_gy": fit["TD50_gy"], "m": fit["m"]}, dose_metric=[10.0, 35.0, 60.0]
    )
    assert p[0] < p[1] < p[2]


def test_mle_refit_is_bounded_and_flags_unidentifiable_fits():
    """With no dose-response the likelihood is flat; the refit must NOT run away.

    Regression guard: an unbounded optimiser produced TD50 ~ 1e16 Gy and a calibration slope
    of ~-1e14 on a real cohort — numbers that are meaningless and would be indefensible in a
    manuscript. The fit is now bounded to the data-supported dose range and reports
    ``plausible=False`` when it cannot be identified.
    """
    rng = np.random.default_rng(11)
    dose = rng.uniform(10, 60, 80)
    y = rng.integers(0, 2, 80)  # outcome independent of dose -> flat likelihood

    fit = fit_ntcp_mle("lkb_probit", dose, y)
    assert fit["TD50_gy"] <= 200.0, "TD50 must stay physically bounded"
    assert 0.02 <= fit["m"] <= 1.5
    lo, hi = fit["td50_bounds"]
    assert lo <= fit["TD50_gy"] <= hi


def test_mle_refit_marks_a_real_dose_response_plausible():
    df = _cohort(200, seed=7)
    fit = fit_ntcp_mle("lkb_probit", df["OAR_gEUD_gy"], df["toxicity"])
    assert fit["plausible"] is True
    assert df["OAR_gEUD_gy"].min() <= fit["TD50_gy"] <= df["OAR_gEUD_gy"].max()


def test_mle_refit_rejects_single_class():
    with pytest.raises(ValueError, match="both outcome classes"):
        fit_ntcp_mle("lkb_probit", [10.0, 20.0, 30.0], [1, 1, 1])


# --------------------------------------------------------------- end-to-end tiers


def test_run_ntcp_benchmark_tiers_and_positive_discrimination():
    df = _cohort(120, seed=1)
    table, extras = run_ntcp_benchmark(
        df,
        endpoint="toxicity",
        model="lkb_probit",
        params={"TD50_gy": 35.0, "m": 0.3},
        dose_metric_col="OAR_gEUD_gy",
        covariate_cols=["OAR_Dmean_gy"],
        dosiomics_cols=["OAR_gEUD_gy", "OAR_Dmean_gy", "OAR_dose_std_gy"],
        groups_col="centre",
        n_splits=4,
    )
    tiers = set(table["tier"])
    assert {"T1", "T2"}.issubset(tiers)
    assert extras["classical_is_engine_model"] is True
    assert extras["model"] == "lkb_probit"
    # With a genuine positive dose-response, the fixed engine model must beat chance.
    t1 = table.set_index("tier").loc["T1"]
    assert t1["apparent_auc"] > 0.65, f"engine classical should discriminate, got {t1}"
    assert str(t1["model"]).startswith("engine_")


# --------------------------------------------------------------- missing OAR dose


def test_patients_without_oar_dose_are_excluded_not_imputed():
    """A missing OAR contour has no computable NTCP -> exclude and count it.

    Imputing 0.0 would fabricate a 'no complication' patient and bias the classical tier
    (and violate the engine's NaN-not-zero contract).
    """
    df = _cohort(60, seed=5)
    df.loc[df.index[:3], "OAR_gEUD_gy"] = np.nan  # 3 patients lack the contour

    table, extras = run_ntcp_benchmark(
        df,
        endpoint="toxicity",
        model="lkb_probit",
        params={"TD50_gy": 35.0, "m": 0.3},
        dose_metric_col="OAR_gEUD_gy",
        dosiomics_cols=["OAR_gEUD_gy", "OAR_Dmean_gy"],
        n_splits=3,
    )
    assert extras["n_excluded_missing_dose"] == 3
    assert extras["n"] == 57
    assert not table["apparent_auc"].isna().all()  # metrics computed, no NaN crash


def test_single_class_after_exclusion_is_a_clear_error():
    df = pd.DataFrame({"toxicity": [1, 1, 1, 0], "OAR_gEUD_gy": [40.0, 45.0, 50.0, float("nan")]})
    with pytest.raises(ValueError, match="single class after excluding"):
        run_ntcp_benchmark(
            df,
            endpoint="toxicity",
            model="lkb_probit",
            params={"TD50_gy": 35.0, "m": 0.3},
            dose_metric_col="OAR_gEUD_gy",
        )


# --------------------------------------------------------------- TCP/NTCP separation


def test_ntcp_module_never_uses_the_tcp_classical():
    """`classical_t1` (PTV_EQD2, TCD50=63.5, returns 1-TCP) is TCP-only.

    Checked on the AST (imports + referenced names), so prose in the module docstring
    explaining the rule does not trip the guard.
    """
    import ast

    tree = ast.parse(inspect.getsource(nb))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom | ast.Import):
            imported.update(a.name for a in node.names)
    assert "classical_t1" not in imported, "NTCP path must not import the TCP predictor"

    referenced = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    referenced |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for banned in ("classical_t1", "_TCD50_EQD2", "_DOSE_DRIVER"):
        assert banned not in referenced, f"NTCP path must not reference TCP symbol {banned}"


def test_tcp_classical_stays_in_the_tcp_module():
    from validation import extval_benchmark as eb

    assert hasattr(eb, "classical_t1")  # still available for the TCP arm
    # ...and the TCP module does not import the NTCP benchmark (no circular coupling).
    assert "ntcp_benchmark" not in inspect.getsource(eb)
