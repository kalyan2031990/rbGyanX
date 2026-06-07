"""MLE fitting of LKB probit NTCP parameters from outcome + DVH cohort data."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml
from scipy.optimize import minimize
from scipy.special import ndtr

logger = logging.getLogger(__name__)


@dataclass
class FittedNTCPParams:
    organ: str
    site: str
    TD50_gy: float
    m: float
    n: float
    TD50_ci: tuple[float, float]
    m_ci: tuple[float, float]
    n_patients: int
    n_events: int
    converged: bool


def _lkb_probit_ntcp(geud: float, td50: float, m: float) -> float:
    if m <= 0 or td50 <= 0:
        return math.nan
    t = (geud - td50) / (m * td50)
    return float(ndtr(t))


def _compute_geud(doses: np.ndarray, vols: np.ndarray, n: float) -> float:
    if n <= 0 or len(doses) == 0:
        return math.nan
    vols_norm = vols / vols.sum() if vols.sum() > 0 else vols
    return float(np.sum(vols_norm * doses ** (1.0 / n)) ** n)


def _neg_log_likelihood_lkb(
    td50: float,
    m: float,
    n: float,
    dvh_list: list[dict],
    outcomes: np.ndarray,
) -> float:
    """Core NLL — exposed for testability (CURSOR_FIXES §25)."""
    if td50 <= 0 or m <= 0 or n <= 0 or n > 1.5:
        return 1e10
    nll = 0.0
    for dvh, yi in zip(dvh_list, outcomes):
        geud = _compute_geud(dvh["doses"], dvh["vols"], n)
        if math.isnan(geud):
            continue
        p = max(1e-9, min(1 - 1e-9, _lkb_probit_ntcp(geud, td50, m)))
        nll -= float(yi) * math.log(p) + (1 - float(yi)) * math.log(1 - p)
    return nll


def _nll_lkb_fixed_n(params, dvh_list, outcomes, n_fixed):
    """Negative log-likelihood for LKB probit with fixed n."""
    td50, m = params
    return _neg_log_likelihood_lkb(td50, m, n_fixed, dvh_list, outcomes)


def _nll_lkb_free(params, dvh_list, outcomes):
    """Negative log-likelihood for LKB probit with free n."""
    td50, m, n = params
    return _neg_log_likelihood_lkb(td50, m, n, dvh_list, outcomes)


def _bootstrap_ci_lkb(
    dvh_list,
    outcomes,
    td50_fit,
    m_fit,
    init_n,
    fix_n,
    n_bootstrap,
    bounds_td50,
    bounds_m,
):
    """Bootstrap 95% CI. Returns (NaN, NaN) with warning if data too sparse."""
    y = np.asarray(outcomes, dtype=float)
    n_events = int(y.sum())
    n_nonevents = int((1 - y).sum())

    if n_events < 5 or n_nonevents < 5:
        logger.warning(
            "Bootstrap CI skipped: too few events (%d) or non-events (%d). "
            "Need ≥5 of each for reliable CI. Collect more outcome data.",
            n_events,
            n_nonevents,
        )
        return (math.nan, math.nan), (math.nan, math.nan)

    td50_boot: list[float] = []
    m_boot: list[float] = []
    rng = np.random.default_rng(42)
    n = len(y)
    successes = 0

    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        y_b = y[idx]
        if y_b.sum() < 2 or (1 - y_b).sum() < 2:
            continue
        dvh_b = [dvh_list[i] for i in idx]
        if fix_n:
            r = minimize(
                _nll_lkb_fixed_n,
                x0=[td50_fit, m_fit],
                args=(dvh_b, y_b, init_n),
                method="L-BFGS-B",
                bounds=[bounds_td50, bounds_m],
            )
        else:
            r = minimize(
                _nll_lkb_free,
                x0=[td50_fit, m_fit, init_n],
                method="L-BFGS-B",
                bounds=[bounds_td50, bounds_m, (0.01, 1.5)],
                args=(dvh_b, y_b),
            )
        if r.success:
            td50_boot.append(r.x[0])
            m_boot.append(r.x[1])
            successes += 1

    if successes < 20:
        logger.warning(
            "Only %d/%d bootstrap resamples converged for CI. "
            "CI may be unreliable.",
            successes,
            n_bootstrap,
        )

    def _ci(arr):
        if len(arr) < 10:
            return (math.nan, math.nan)
        return (float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5)))

    return _ci(td50_boot), _ci(m_boot)


def fit_lkb_parameters(
    dvh_list: list[dict],
    outcomes: np.ndarray,
    organ: str,
    site: str,
    init_td50: float = 50.0,
    init_m: float = 0.15,
    init_n: float = 0.25,
    n_bootstrap: int = 200,
    fix_n: bool = True,
) -> FittedNTCPParams:
    """Fit LKB probit TD50 and m by maximum likelihood (n fixed by default)."""
    y = np.asarray(outcomes, dtype=float)
    n_patients = len(y)
    n_events = int(y.sum())

    bounds = [(10.0, 150.0), (0.01, 0.5)]
    if fix_n:
        res = minimize(
            _nll_lkb_fixed_n,
            x0=[init_td50, init_m],
            args=(dvh_list, y, init_n),
            method="L-BFGS-B",
            bounds=bounds,
        )
        td50_fit, m_fit = (res.x[0], res.x[1]) if res.success else (init_td50, init_m)
    else:
        res = minimize(
            _nll_lkb_free,
            x0=[init_td50, init_m, init_n],
            args=(dvh_list, y),
            method="L-BFGS-B",
            bounds=[(10.0, 150.0), (0.01, 0.5), (0.01, 1.5)],
        )
        td50_fit, m_fit = (res.x[0], res.x[1]) if res.success else (init_td50, init_m)

    td50_ci, m_ci = (math.nan, math.nan), (math.nan, math.nan)
    if n_bootstrap > 0:
        td50_ci, m_ci = _bootstrap_ci_lkb(
            dvh_list,
            y,
            td50_fit,
            m_fit,
            init_n,
            fix_n,
            n_bootstrap,
            bounds[0],
            bounds[1],
        )

    return FittedNTCPParams(
        organ=organ,
        site=site,
        TD50_gy=round(td50_fit, 2),
        m=round(m_fit, 4),
        n=round(init_n, 4),
        TD50_ci=td50_ci,
        m_ci=m_ci,
        n_patients=n_patients,
        n_events=n_events,
        converged=bool(res.success),
    )


def fitted_params_to_yaml(fitted: list[FittedNTCPParams], site: str) -> str:
    organs = {}
    for p in fitted:
        organs[p.organ] = {
            "canonical": p.organ,
            "lkb_probit": {
                "TD50_gy": p.TD50_gy,
                "m": p.m,
                "n": p.n,
                "_fit_note": f"MLE n={p.n_patients} events={p.n_events} converged={p.converged}",
            },
        }
    return yaml.dump({site: {"organs": organs}}, default_flow_style=False, sort_keys=False)


def write_fitted_yaml(fitted: list[FittedNTCPParams], site: str, path: Path) -> Path:
    path = Path(path)
    path.write_text(fitted_params_to_yaml(fitted, site), encoding="utf-8")
    return path


def _dvh_df_to_fit_dict(dvh_df) -> dict:
    import pandas as pd

    df = pd.DataFrame(dvh_df)
    dose_col = "dose_gy" if "dose_gy" in df.columns else df.columns[0]
    vol_col = "volume_frac" if "volume_frac" in df.columns else df.columns[1]
    return {
        "doses": df[dose_col].astype(float).to_numpy(),
        "vols": df[vol_col].astype(float).to_numpy(),
    }


def calibrate_ntcp_from_results(
    ntcp_results: list[dict],
    outcome_csv: Path,
    site: str,
    output_dir: Path,
    min_patients: int = 10,
    min_events: int = 5,
) -> Path | None:
    """Fit LKB probit per organ from engine rows with ``_dvh_df`` and outcome CSV."""
    import pandas as pd

    outcomes = pd.read_csv(outcome_csv)
    if "ntcp_outcome" not in outcomes.columns:
        logger.error("outcome CSV missing ntcp_outcome column")
        return None
    by_pid = outcomes.set_index(outcomes["AnonPatientID"].astype(str))["ntcp_outcome"]
    fitted: list[FittedNTCPParams] = []
    for organ in {r.get("structure") for r in ntcp_results if r.get("structure")}:
        dvh_list: list[dict] = []
        y_list: list[float] = []
        for r in ntcp_results:
            if r.get("structure") != organ:
                continue
            pid = str(r.get("AnonPatientID", ""))
            if pid not in by_pid.index:
                continue
            dvh_df = r.get("_dvh_df")
            if dvh_df is None:
                continue
            dvh_list.append(_dvh_df_to_fit_dict(dvh_df))
            y_list.append(float(by_pid.loc[pid]))
        if len(dvh_list) < min_patients or sum(y_list) < min_events:
            continue
        init_td50 = 50.0
        init_m = 0.15
        init_n = 0.25
        for r in ntcp_results:
            if r.get("structure") == organ and r.get("gEUD_gy"):
                init_td50 = float(r.get("gEUD_gy", init_td50))
                break
        fitted.append(
            fit_lkb_parameters(
                dvh_list,
                np.asarray(y_list),
                organ=str(organ),
                site=site,
                init_td50=init_td50,
                init_m=init_m,
                init_n=init_n,
            )
        )
    if not fitted:
        logger.warning("No organs met minimum cohort size for NTCP calibration.")
        return None
    out = Path(output_dir) / "site_params_fitted.yaml"
    return write_fitted_yaml(fitted, site, out)
